import unittest
from unittest.mock import patch
import system_service as service


class XnodeAllowlistTests(unittest.TestCase):
    def test_configured_node_read_only_xnode_is_allowed(self):
        for parrot_active in (False, True):
            with patch.object(service,'load_state',return_value={'node':'12345'}), \
                 patch.object(service,'cli',return_value='synthetic telemetry') as cli, \
                 patch.object(type(service.RADIO_PARROT),'active',new_callable=lambda: property(lambda self: parrot_active)):
                self.assertEqual(service.handle({'action':'cli','command':'rpt xnode 12345'}),{'output':'synthetic telemetry'})
                cli.assert_called_once_with('rpt xnode 12345')

    def test_other_nodes_arguments_and_injection_are_rejected(self):
        for command in ('rpt xnode 54321','rpt xnode','rpt xnode 12345 extra','rpt xnode 12345; shell',
                        'rpt xnode 12345\n','rpt xnode 12345\nrpt cmd 12345 ilink 3 54321',
                        'rpt xnode 123450','rpt xnode 012345',None):
            with self.subTest(command=command), patch.object(service,'load_state',return_value={'node':'12345'}), \
                 patch.object(service,'cli') as cli:
                with self.assertRaises(ValueError):service.handle({'action':'cli','command':command})
                cli.assert_not_called()


if __name__=='__main__':unittest.main()
