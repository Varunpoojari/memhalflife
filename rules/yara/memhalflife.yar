/*
  MemHalfLife detection rules — string/indicator based, for scanning memory
  images (Volatility 3 yarascan / vadyarascan / vmayarascan) or live memory
  dumps. They target *command lines and artefacts* of LOTL techniques, not
  payload bytes, and are intended for DFIR triage. Expect false positives on
  admin tooling; always corroborate with process context.
  Licence: MIT.
*/

rule MemHL_PS_DownloadCradle
{
    meta:
        description = "PowerShell download-cradle indicators in memory"
        attack = "T1059.001"
        severity = "medium"
    strings:
        $a1 = "DownloadString" ascii wide nocase
        $a2 = "Net.WebClient" ascii wide nocase
        $a3 = "Invoke-WebRequest" ascii wide nocase
        $a4 = "Invoke-Expression" ascii wide nocase
        $a5 = /\bIEX\s*\(/ ascii wide nocase
        $u  = /https?:\/\/[0-9a-z\.\-:]+\// ascii wide nocase
    condition:
        $u and 2 of ($a*)
}

rule MemHL_Mshta_Remote_Script
{
    meta:
        description = "mshta executing a remote or script-protocol target"
        attack = "T1218.005"
        severity = "medium"
    strings:
        $m = /mshta(\.exe)?"?\s+(https?:\/\/|vbscript:|javascript:)/ ascii wide nocase
    condition:
        $m
}

rule MemHL_Regsvr32_Scriptlet
{
    meta:
        description = "regsvr32 loading a remote scriptlet via scrobj.dll"
        attack = "T1218.010"
        severity = "medium"
    strings:
        $r = "regsvr32" ascii wide nocase
        $i = /\/i:https?:\/\// ascii wide nocase
        $s = "scrobj.dll" ascii wide nocase
    condition:
        $r and ($i or $s)
}

rule MemHL_WMI_EventConsumer
{
    meta:
        description = "WMI permanent event subscription objects"
        attack = "T1546.003"
        severity = "high"
    strings:
        $consumer1 = "CommandLineEventConsumer" ascii wide
        $consumer2 = "ActiveScriptEventConsumer" ascii wide
        $filter    = "__EventFilter" ascii wide
        $binding   = "__FilterToConsumerBinding" ascii wide
    condition:
        1 of ($consumer*) and ($filter or $binding)
}

rule MemHL_LSASS_Dump_Tooling
{
    meta:
        description = "Command-line or module strings associated with LSASS credential dumping"
        attack = "T1003.001"
        severity = "high"
    strings:
        $comsvcs = "comsvcs.dll" ascii wide nocase
        $minidump = "MiniDump" ascii wide
        $sek = "sekurlsa::" ascii wide nocase
        $procdump = /procdump(64)?(\.exe)?\s.*lsass/ ascii wide nocase
    condition:
        ($comsvcs and $minidump) or $sek or $procdump
}

rule MemHL_Linux_IMDS_Credential_Query
{
    meta:
        description = "Query of the cloud instance metadata service for credentials/tokens"
        attack = "T1552.005"
        severity = "medium"
    strings:
        $ip = "169.254.169.254" ascii wide
        $c1 = "security-credentials" ascii
        $c2 = "api/token" ascii
        $c3 = "identity/oauth2/token" ascii
    condition:
        $ip and 1 of ($c*)
}

rule MemHL_Linux_Memfd_Execution
{
    meta:
        description = "Anonymous-memory (memfd) file references used for fileless ELF execution"
        attack = "T1620"
        severity = "medium"
    strings:
        $m1 = "/memfd:" ascii
        $m2 = /\/proc\/self\/fd\/[0-9]+/ ascii
        $del = "(deleted)" ascii
    condition:
        $m1 and ($del or $m2)
}

rule MemHL_Linux_DevTcp_Reverse_Shell
{
    meta:
        description = "Bash /dev/tcp redirection typical of a reverse shell"
        attack = "T1059.004"
        severity = "high"
    strings:
        $d = /\/dev\/tcp\/[0-9]{1,3}(\.[0-9]{1,3}){3}\/[0-9]{1,5}/ ascii
        $s = /(ba)?sh -i/ ascii
    condition:
        $d and $s
}
