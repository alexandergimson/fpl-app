from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.api import main


class ApiTests(unittest.TestCase):
    def test_refresh_invokes_existing_job_and_returns_summary(self):
        summary = {
            "status": "SUCCESS",
            "gameweek": 3,
            "players": 640,
            "fixtures": 380,
            "observations": 640,
            "team_underlying": 40,
            "materialized": 640,
            "snapshots": 15,
            "alerts": 2,
        }
        with patch("backend.api.main.refresh_all", return_value=summary) as refresh_all:
            response = main.post_refresh()
        self.assertEqual(response, summary)
        refresh_all.assert_called_once_with(season="2026-27", par_season="2026-27")

    def test_refresh_returns_conflict_when_already_running(self):
        self.assertTrue(main._refresh_lock.acquire(blocking=False))
        try:
            with patch("backend.api.main.refresh_all") as refresh_all:
                with self.assertRaises(HTTPException) as error:
                    main.post_refresh()
        finally:
            main._refresh_lock.release()
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(error.exception.detail, "Refresh already running")
        refresh_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
