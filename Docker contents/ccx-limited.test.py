import importlib.util
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

spec = importlib.util.spec_from_file_location('limited', Path(__file__).with_name('ccx-limited.py'))
limited = importlib.util.module_from_spec(spec)
spec.loader.exec_module(limited)


class ModalLimitTests(unittest.TestCase):
    def test_detects_modal_includes_and_ignores_static_and_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deck = root / 'job.inp'
            deck.write_text('** *FREQUENCY\n*STATIC\n')
            self.assertFalse(limited.is_modal(deck))
            deck.write_text('*INCLUDE, INPUT=modes.inp\n')
            (root / 'modes.inp').write_text('*include, input=job.inp\n *frequency, solver=ARPACK\n')
            self.assertTrue(limited.is_modal(deck))

    def test_exactly_15_concurrent_attempts_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'count'
            state.write_text('0')
            def attempt(_):
                try:
                    limited.reserve(state)
                    return True
                except RuntimeError:
                    return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(attempt, range(40))), 15)
            self.assertEqual(state.read_text(), '15')
            with self.assertRaisesRegex(RuntimeError, '15 runs'):
                limited.reserve(state)


if __name__ == '__main__':
    unittest.main()
