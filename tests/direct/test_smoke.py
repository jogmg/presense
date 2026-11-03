"""Phase 0 smoke tests: the contract loads and exposes its version."""


def test_contract_deploys_and_reports_version(direct_deploy):
    contract = direct_deploy("contracts/Presense.py")
    assert contract.get_version() == "0.1.0"
