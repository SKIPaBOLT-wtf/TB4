from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_plan_preserves_history_and_has_separate_verifiable_steps():
    plan = yaml.safe_load((ROOT / 'docs/implementation-plan/manifest.yaml').read_text())
    assert all(plan['steps'][f'IP-{n:02d}']['status'] == 'VERIFIED' for n in range(1, 60))
    assert plan['steps']['IP-60']['status'] == 'SUPERSEDED'
    assert plan['steps']['IP-61']['status'] == 'SUPERSEDED'
    assert 'private-environment-prerequisite-audit' in plan['steps']['IP-60']['evidence'][0]
    for number in range(62, 71):
        identity = f'IP-{number}'
        assert identity in plan['steps']
        matches = list((ROOT / 'docs/implementation-plan/steps').glob(f'{identity}-*.md'))
        assert len(matches) == 1
        text = matches[0].read_text()
        for heading in ('Purpose', 'Preconditions', 'Inputs / authoritative references', 'Work',
                        'Files / modules', 'Required invariants', 'Tests', 'Failure cases',
                        'Completion evidence required', 'Handoff state', 'Amendment path', 'Evidence path'):
            assert f'## {heading}' in text
    assert plan['steps']['IP-68']['title'] == 'Private Same-Host Desktop Pilot'
    assert plan['steps']['IP-69']['title'] == 'Independent-Machine Expansion Pilot'


def test_desktop_contract_is_explicit_about_mounts_and_safety():
    text = (ROOT / 'docs/DESKTOP.md').read_text()
    for clause in ('not remote confirmation', 'A running process', 'No listening',
                   'Preserve private configuration', 'not evidence of an independent two-machine'):
        assert clause in text
