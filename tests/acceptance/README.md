# Acceptance tests

End-to-end checks of Beliefline: 89 file(s), each checking one thing a user, an operator or an attacker could do, through the product's real interface. The helpers in `_helpers/` drive that interface.

Run them from the repository root (they need pytest):

    python -m pytest tests/acceptance

## Known open items

These tests are marked as expected failures (`xfail`): the behaviour they check isn't there yet, so the suite stays green. Each one passes (XPASS) once it is fixed; then delete the mark at the end of its file.

- `test_database_file_data_dir_not_readable_other_local_users.py`: Known security issue (low): The database file in the data dir is not readable by other local users
- `test_out_range_report_time_range_non_string_setting_key_returns.py`: Known security issue (low): An out-of-range report time range or a non-string setting key returns 400, never 500
