"""A probe is evidence about its actual host, never remote-storage qualification."""
from tools.experiments.folder_journal import probe


def test_persistent_exclusive_journal_keeps_fixed_objects_and_rolls_back_crashed_writer(tmp_path):
    result=probe(tmp_path/"fixed-folder-probe")
    assert result["initial_revision"] == 1 and result["committed_revision"] == 2
    assert result["concurrent_outcomes"] in (["ACCEPTED","REJECTED"],["ACCEPTED","BUSY"])
    assert result["stale_revision_after_release"] == "REJECTED"
    assert result["stale_recheck_preserved_commit"]
    assert result["uncommitted_database_pages_changed"]
    assert result["reopened_matches_last_committed"]
    assert result["same_fixed_names"] and result["same_file_identities"]
    assert result["missing_journal_rejected"] and result["no_missing_journal_recreation"]
    assert all(size <= 2*1024*1024 for size in result["final_sizes"].values())
    assert not result["actual_power_loss_test"] and not result["remote_ssh_test"] and not result["production_qualified"]
