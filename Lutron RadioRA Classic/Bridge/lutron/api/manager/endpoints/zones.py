import os
import json
import logging

from flask import request
from flask_restplus import Resource
from lutron.api.manager.dbmethods import create_zone, update_zone, delete_zone
from lutron.api.manager.serializers import zone, zonetype, zonetype_with_zones
from lutron.api.restplus import api
from lutron.database.models import Zone, Zonetype

log = logging.getLogger(__name__)

# FIXME: what must be configured
#  - for each zone, what zone type of switch/dimmer it is (default to dimmer)
#  - we should allow client to specify if they want ALL the zones (e.g. including Unassigned)

ns = api.namespace('zones', description='Zone operations')

raSerial = None

# FIXME: this will not work on Lutron installations where a Chronos System Bridge or
# Timeclock is setup to be a System Bridge where TWO zone maps will be returned (a total of 64 zones)
def getAllZoneStates():
    raSerial.writeCommand("ZMPI")
    zoneStates = raSerial.readData().lstrip('ZMP')
    return zoneStates

def mergeZoneStates(zones, stateZMP):
    # NOTE: ZMP always returns state for all 32 zones, PLUS if it is a bridged system
    # it will return two sets, with ",S1" and ",S2" at the end of the result
    # this does not support bridged systems currently
    if type(zones) is list:
        for index, item in enumerate(zones):
            if stateZMP[item.zone] == '0':
                zones[index].state = 'off'
            elif stateZMP[item.zone] == '1':
                zones[index].state = 'on'
            elif stateZMP[item.zone] == 'X':
                # force type to be Unassigned (since we know it isn't assigned to a dimmer or switch)
                zones[index].zonetypeid  = '0' # Unassigned
                zones[index].state = 'Unknown'
            else:
                zones[index].state = 'Unknown'
    else:
        if stateZMP[zones.zone] == '0':
            zones.state = 'off'
        elif stateZMP[zones.zone] == '1':
            zones.state = 'on'
        elif stateZMP[zones.zone] == 'X':
            # force type to be Unassigned (since we know it isn't assigned to a dimmer or switch)
            zones.zonetypeid = '0' # Unassigned
            zones.state = 'Unknown'
        else:
            zones.state = 'Unknown'

    return zones   

@ns.route('/')
class ZoneCollection(Resource):
    
    @api.marshal_list_with(zone)
    def get(self):
        # read zone configuration from DB
        zones = Zone.query.all()
        # merge current states for each zone from hardware module
        zones = mergeZoneStates(zones, getAllZoneStates())        
        return zones

####

@ns.route('/<int:id>')
@api.response(404, 'Zone not found')
class ZoneItem(Resource):

    @api.marshal_with(zone)
    def get(self, id):
        return mergeZoneStates(Zone.query.filter(Zone.id == id).one(), getAllZoneStates())

    @api.expect(zone)
    @api.response(204, 'Zone successfully updated')
    def put(self, id):
        """
        Update attributes for a zone

        Send a JSON object with the new name in the request body with the ID of the zone to modify in the request URL path.

        ```
        {
          "name": "Zone name"
          "zonetypeid": "Zone type identifier [0, 1, 2, or 3]"
          "default_level": "Default level for dimmer (not yet supported)"
        }
        ```
        """
        data = request.json
        update_zone(id, data)
        return None, 204

# FIXME: I'm not sure we want REST Get with side effect, but it is very convenient!
@ns.route('/<int:id>/dim/<level>')
class ZoneDimmerLevel(Resource):
    def get(self, zone, level):
        # SDL,<Zone Number>,<Dimmer Level>(,<Fade Time>){(,<System)}
        raSerial.writeCommand("SDL," + zone + "," + level)
        return {'lutron': raSerial.readData()}

@ns.route('/<int:id>/switch/on')
class ZoneSwitchOn(Resource):
    def get(self, zone):
        # SSL,<Zone Number>,<State>(,<Delay Time>){(,<System>)}
        raSerial.writeCommand("SSL," + zone + ",ON")
        return {'lutron': raSerial.readData()}

@ns.route('/<int:id>/switch/off')
class ZoneSwitchOff(Resource):
    def get(self, zone):
        raSerial.writeCommand("SSL," + zone + ",OFF")
        return {'lutron': raSerial.readData()}

@ns.route('/all/on')
class AllOn(Resource):
    def get(self):
        raSerial.writeCommand("BP,16,ON")
        return {'lutron': raSerial.readData()}

@ns.route('/all/off')
class AllOff(Resource):
    def get(self):
        raSerial.writeCommand("BP,17,OFF")
        return {'lutron': raSerial.readData()}

@ns.route('/all/flash/on')
class FlashOn(Resource):
    def get(self):
        raSerial.writeCommand("SFM,16,ON")
        return {'lutron': raSerial.readData()}

@ns.route('/all/flash/off')
class FlashOff(Resource):
    def get(self):
        raSerial.writeCommand("SFM,17,OFF")
        return {'lutron': raSerial.readData()}