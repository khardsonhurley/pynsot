# -*- coding: utf-8 -*-

"""
Test Protocols in the CLI app.
"""

from __future__ import absolute_import, unicode_literals
import logging

import pytest

from tests.fixtures import (attribute, attributes, client, config, device,
                            interface, network, protocol_type, site, site_client)
from tests.fixtures.circuits import (circuit, circuit_attributes, interface_a,
                                    interface_z, device_a, device_z)
from tests.fixtures.protocols import protocol

from tests.util import CliRunner, assert_output

log = logging.getLogger(__name__)


def test_protocols_add(site_client, device, interface, site, protocol_type):
    """Test ``nsot protocol add``."""

    device_id = str(device['id'])
    interface_id = str(interface['id'])

    runner = CliRunner(site_client.config)
    with runner.isolated_filesystem():
        # Add a protocol.
        result = runner.run(
            "protocols add -t bgp -D %s -i %s -e 'my new proto'" % (device_id, interface_id)
        )
        assert result.exit_code == 0
        assert 'Added protocol!' in result.output

        # Verify addition.
        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'bgp' in result.output
        assert device_id in result.output
        assert 'my new proto' in result.output


def test_protocols_list(site_client, device_a, interface_a, site, circuit, protocol):
    """Test ``nsot protocols list``"""

    device_id = str(device_a['id'])
    interface_id = str(interface_a['id'])

    runner = CliRunner(site_client.config)
    with runner.isolated_filesystem():

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'bgp' in result.output

        # Test -D/--device
        result = runner.run('protocols list -t bgp -D %s' % device_id)
        assert result.exit_code == 0
        assert device_a['hostname'] in result.output

        # Test -i/--interface
        result = runner.run('protocols list -t bgp -i %s' % interface_id)
        assert result.exit_code == 0
        assert interface_id in result.output

        # Test -a/--attributes
        result = runner.run('protocols list -t bgp -a foo=test_protocol')
        assert result.exit_code == 0
        assert protocol['attributes']['foo'] in result.output

        # Test -c/--circuit
        result = runner.run('protocols list -t bgp -c %s' % circuit['name'])
        assert result.exit_code == 0
        assert circuit['name'] in result.output

        # Test -e/--description
        result = runner.run('protocols list -t bgp -e %s' % protocol['description'])
        assert result.exit_code == 0
        assert protocol['description'] in result.output

        # Test -I/--id
        result = runner.run('protocols list -t bgp -I 1')
        assert result.exit_code == 0
        assert protocol['id'] in result.output


def test_protocols_update(site_client, interface_a, device_a, site, circuit, protocol):
    site_id = str(protocol['site'])

    runner = CliRunner(site_client.config)
    with runner.isolated_filesystem():
        # Update description
        result = runner.run('protocols update -t bgp -D %s -e "bees buzz"' % (device_a['hostname']))
        assert result.exit_code == 0
        assert 'Updated protocol!' in result.output

        # Ensure that buzz is not the bizness
        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'buzz' in result.output
        assert 'bizness' not in result.output

        # Add an attribute
        result = runner.run('protocols update -t bgp -D %s --add-attributes -a boo=test_attribute' % device_a['hostname'])
        # assert result.exit_code == 0
        # assert 'Updated protocol!' in result.output

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        # assert 'test_attribute' in result.output

        # Edit an attribute
        result = runner.run('protocols update -t bgp -D %s -a foo=test_attribute' % device_a['hostname'])
        assert result.exit_code == 0
        assert 'Updated protocol!' in result.output

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'test_attribute' in result.output

        # Delete an attribute
        result = runner.run('protocols update -t bgp -D %s --delete-attributes -a foo=test_protocol' % device_a['hostname'])
        assert result.exit_code == 0
        assert 'Updated protocol!' in result.output

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'test_protocol' not in result.output

        # Replace an attribute
        result = runner.run('protocols update -t bgp -D %s --replace-attributes -a foo=test_replace' % device_a['hostname'])
        assert result.exit_code == 0
        assert 'Updated protocol!' in result.output

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'test_protocol' not in result.output
        assert 'test_replace' in result.output



def test_protocols_remove(site_client, protocol):
    site_id = protocol['site']
    runner = CliRunner(site_client.config)

    with runner.isolated_filesystem():
        result = runner.run('protocols remove -I %s -s %s' % (site_id, protocol['site']))
        assert result.exit_code == 0

        result = runner.run('protocols list -t bgp')
        assert result.exit_code == 0
        assert 'No protocol found' in result.output
