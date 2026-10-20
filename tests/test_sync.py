import unittest
from unittest.mock import patch
from upkeep.cli import cmd_sync

class TestSync(unittest.TestCase):
    def setUp(self):
        self.config = {"apps": [
            {"name": "app1", "repo": "repo1"},
            {"name": "app2", "repo": "repo2"}
        ]}

    @patch('upkeep.cli.cmd_update')
    def test_sync_all_apps(self, mock_update):
        args = type('', (), {})()  # Create a dummy object
        args.names = []  # Simula nessun nome specificato
        cmd_sync(self.config, args)
        mock_update.assert_called_once_with(self.config, args, skip_confirm=True)

    @patch('upkeep.cli.cmd_update')
    def test_sync_specific_app(self, mock_update):
        args = type('', (), {})()  # Create a dummy object
        args.names = ["app1"]  # Simula richiesta di sincronizzazione di 'app1'
        cmd_sync(self.config, args)
        mock_update.assert_called_once_with(self.config, args, skip_confirm=True)

    @patch('upkeep.cli.cmd_update')
    def test_sync_forwards_names(self, mock_update):
        args = type('', (), {})()  # Create a dummy object
        args.names = ["unknown_app"]  # Simula richiesta di un'app sconosciuta
        cmd_sync(self.config, args)
        mock_update.assert_called_once_with(self.config, args, skip_confirm=True)

if __name__ == '__main__':
    unittest.main()
