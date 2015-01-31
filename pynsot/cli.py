# -*- coding: utf-8 -*-

"""
Base CLI commands for all objects. Model-specific objects and argument parsers
will be defined in subclasses or by way of factory methods.
"""

__author__ = 'Jathan McCollum'
__maintainer__ = 'Jathan McCollum'
__email__ = 'jathan@dropbox.com'
__copyright__ = 'Copyright (c) 2015 Dropbox, Inc.'


import click
import logging
import sys
import tabulate
import os

from slumber.exceptions import HttpClientError
import pynsot
from pynsot.client import Client, ClientError
from pynsot.models import ApiModel


# Constants/Globals
log = logging.getLogger(__name__)

# Let's hard code these for now until we have dotfile system in place.
URL = 'http://localhost:8990/api'
EMAIL = 'jathan@localhost'

# Make the --help option also have -h
CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
)

# Used to map human-readable action names to API calls.
ACTION_MAP = {
    'add': 'post',
    'list': 'get',
    'remove': 'delete',
    'update': 'patch',
}

# Mapping of objec field names to their human-readable form used when calling
# .print_list() for an object type.
FIELDS_MAP = {
    'id': 'ID',
    'name': 'Name',
    'description': 'Description',
}


# Where to find the command plugins.
CMD_FOLDER = os.path.abspath(os.path.join(
                             os.path.dirname(__file__), 'commands'))


class CLI(click.MultiCommand):
    """
    Base command object used to define object-specific command-line parsers.

    This will load command plugins from the "commands" folder

    Plugins must be named "cmd_{foo}.py"
    """
    def list_commands(self, ctx):
        """List all commands from python modules in plugin folder."""
        rv = []
        for filename in os.listdir(CMD_FOLDER):
            if filename.endswith('.py') and filename.startswith('cmd_'):
                rv.append(filename[4:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        """Import a command module and return it."""
        try:
            if sys.version_info[0] == 2:
                name = name.encode('ascii', 'replace')
            mod = __import__('pynsot.commands.cmd_' + name,
                             None, None, ['app'])
        except ImportError as err:
            print err
            return None
        return mod.cli


class App(object):
    """Context object for holding state data."""
    def __init__(self, url, email, ctx, verbose=False):
        self.api = Client(url, email=email)
        self.ctx = ctx
        self.verbose = verbose
        self.resource_name = self.ctx.invoked_subcommand

    @property
    def singular(self):
        """Return singular form of resource name."""
        resource_name = self.resource_name
        if resource_name.endswith('s'):
            resource_name = resource_name[:-1]
        return resource_name

    @property
    def resource(self):
        """Return an API resource method."""
        return self.api.get_resource(self.resource_name)

    def pretty_dict(self, data):
        """Return a dict in k=v format."""
        pretty = ', '.join('%s=%r' % (k, v) for k, v in data.items())
        return pretty

    def handle_error(self, action, data, err):
        """Handle error API response."""
        pretty_dict = self.pretty_dict(data)
        resp = getattr(err, 'response', None)
        obj_single = self.singular
        if resp is not None:
            t_ = '[FATAL] %s %s trying to %s %s with args: %s'
            msg = t_ % (resp.status_code, resp.reason, action, obj_single,
                        pretty_dict)
        else:
            msg = '[FATAL] %s' % err
        self.ctx.exit(msg)

    def handle_response(self, action, data, result):
        """Handle positive API response."""
        pretty_dict = self.pretty_dict(data)
        t_ = 'Successfully %sed %s with args: %s!'
        msg = t_ % (action, self.singular,  pretty_dict)
        click.echo(msg)

    def map_fields(self, fields, fields_map):
        """Map ``fields`` using ``fields_map``."""
        try:
            headers = [fields_map[f] for f in fields]
        except KeyError:
            self.ctx.exit('Could not map field %r when displaying results.')
        return headers

    def print_list(self, objects, fields=None, fields_map=None):
        """
        Print objects in a table format.

        :param objects:
            List of object dicts

        :param fields:
            List of field names to display in order

        :param fields_map:
            Mapping used to translate field names for display
        """
        # Default to using all fields
        if fields is None:
            first_obj = objects[0]  # This better be a list/tuple!
            fields = first_obj.keys()  # This better be a dict!

        # Set the field mapping
        if fields_map is None:
            fields_map = FIELDS_MAP

        # Human-readable field headings as they will be displayed
        tablefmt='simple'
        headers = self.map_fields(fields, fields_map)

        # Order the object key/val by the order in display fields
        table_data = [[obj[f] for f in fields] for obj in objects]
        table = tabulate.tabulate(table_data, headers=headers,
                                  tablefmt=tablefmt)

        # Only paginate if table is longer than terminal.
        t_height, _ = click.get_terminal_size()
        if len(table_data) > t_height:
            click.echo_via_pager(table)
        else:
            click.echo(table)

    def add(self, data):
        action = 'add'
        #log.debug('adding %s %s' % data)
        try:
            result = self.resource.post(data)
        except HttpClientError as err:
            self.handle_error(action, data, err)
        else:
            self.handle_response(action, data, result)

    def list(self, data, fields=None):
        action = 'list'
        #log.debug('listing %s' % data)
        try:
            result = self.resource.get(**data)
        except HttpClientError as err:
            self.handle_error(action, data, err)
        else:
            objects = []
            if result:
                objects = result['data'][self.resource_name]
            if objects:
                self.print_list(objects, fields)
            else:
                pretty_dict = self.pretty_dict(data)
                t_ = 'No %s found matching args: %s!'
                msg = t_ % (self.singular, pretty_dict)
                click.echo(msg)

    def remove(self, **data):
        action = 'remove'
        obj_id = data['id']
        #log.debug('removing %s' % obj_id)
        try:
            result = self.resource(obj_id).delete()
        except HttpClientError as err:
            self.handle_error(action, data, err)
        else:
            self.handle_response(action, data, result)

    def update(self, data):
        action = 'update'
        obj_id = data.pop('id')
        #log.debug('updating %s' % data)

        # Get the original object by id first so that we can keep any existing
        # values without resetting them.
        try:
            obj = self.resource(obj_id).get()
        except HttpClientError as err:
            self.handle_error(action, data, err)
        else:
            model = ApiModel(obj)
            payload = dict(model)
            payload.pop('id')  # We don't want id when doing a PUT

        # Update the payload from the CLI params if the value isn't null..
        for k, v in data.items():
            if v is not None:
                payload[k] = v

        # And now we call PUT
        try:
            result = self.resource(obj_id).put(payload)
        except HttpClientError as err:
            self.handle_error(action, data, err)
        else:
            self.handle_response(action, data, result)


@click.command(cls=CLI, context_settings=CONTEXT_SETTINGS)
@click.version_option(version=pynsot.__version__)
@click.option('-v', '--verbose', is_flag=True, help='Toggle verbosity.')
@click.pass_context
def app(ctx, verbose):
    """NSoT command-line utility."""
    # This is the "app" object attached to all contexts.
    ctx.obj = App(URL, email=EMAIL, ctx=ctx, verbose=verbose)


if __name__ == '__main__':
    app()