import copy
import unittest
from pathlib import Path
from src.switchctl import render, ios_lines

ROOT = Path(__file__).resolve().parents[1]

class TestConfigs(unittest.TestCase):
    def setUp(self):
        self.profile, self.cfg = render(ROOT / 'clients/client-demo.yaml')

    def test_expected_commands(self):
        self.assertIn('switchport access vlan 10', self.cfg)
        self.assertIn('switchport trunk allowed vlan 10,20,30,99,999', self.cfg)
        self.assertIn('spanning-tree bpduguard enable', self.cfg)

    def test_unknown_vlan_rejected(self):
        obj = copy.deepcopy(self.profile)
        obj['interfaces'][0]['vlan'] = 888
        with self.assertRaises(ValueError):
            ios_lines(obj)

    def test_duplicate_interface_rejected(self):
        obj = copy.deepcopy(self.profile)
        obj['interfaces'].append(copy.deepcopy(obj['interfaces'][0]))
        with self.assertRaises(ValueError):
            ios_lines(obj)

    def test_bad_description_rejected(self):
        obj = copy.deepcopy(self.profile)
        obj['interfaces'][0]['description'] = 'foo\nshutdown'
        with self.assertRaises(ValueError):
            ios_lines(obj)

if __name__ == '__main__':
    unittest.main()
