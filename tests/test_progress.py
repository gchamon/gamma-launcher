from unittest import TestCase
from unittest.mock import Mock, patch

from launcher.progress import progress_bar


class ProgressBarTestCase(TestCase):

    @patch('launcher.progress.tqdm')
    @patch('builtins.print')
    def test_non_tty_disables_tqdm_and_prints_once(self, mock_print, mock_tqdm):
        stream = Mock()
        stream.isatty.return_value = False

        with patch('launcher.progress.stderr', stream):
            progress_bar("Downloading file.zip", unit="iB")

        mock_print.assert_called_once_with("[*] Downloading file.zip")
        mock_tqdm.assert_called_once_with(
            desc="Downloading file.zip",
            dynamic_ncols=True,
            ascii=True,
            disable=True,
            unit="iB",
        )

    @patch('launcher.progress.tqdm')
    @patch('builtins.print')
    def test_tty_enables_single_line_tqdm(self, mock_print, mock_tqdm):
        stream = Mock()
        stream.isatty.return_value = True

        with patch('launcher.progress.stderr', stream):
            progress_bar("Downloading file.zip", unit="iB")

        mock_print.assert_not_called()
        mock_tqdm.assert_called_once_with(
            desc="Downloading file.zip",
            dynamic_ncols=True,
            ascii=True,
            disable=False,
            unit="iB",
        )
