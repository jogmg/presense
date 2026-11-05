"""Phase 6: security invariants and exhaustive payout checks."""

import pytest


def test_partial_payout_conservation_for_all_scores_and_escrow_edges(
    direct_deploy,
):
    contract = direct_deploy("contracts/Presense.py")
    escrow_values = (1, 2, 3, 10, 99, 100, 101, 10**18, 10**18 + 7)

    for escrow in escrow_values:
        for score in range(101):
            buyer_payout, seller_payout = contract._compute_payouts(
                escrow, score, "PARTIAL"
            )
            assert buyer_payout + seller_payout == escrow
            assert 0 <= seller_payout <= escrow
            assert seller_payout == (escrow * score) // 100


@pytest.mark.parametrize("score", [0, 1, 50, 99, 100])
def test_accept_and_reject_payout_edges_are_exact(direct_deploy, score):
    contract = direct_deploy("contracts/Presense.py")

    assert contract._compute_payouts(101, score, "ACCEPT") == (0, 101)
    assert contract._compute_payouts(101, score, "REJECT") == (101, 0)


@pytest.mark.parametrize("score", [-1, 101, True])
def test_payout_rejects_invalid_scores(direct_deploy, score):
    contract = direct_deploy("contracts/Presense.py")

    with pytest.raises(Exception, match="E_PAYOUT_INVALID"):
        contract._compute_payouts(101, score, "PARTIAL")