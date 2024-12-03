"""ecoflow.py: API for PowerOcean integration   AJB7."""
""" closely based on code by niltrip modified to cater for dual master/slave inverter configuration  """
""" AndyBowden Dec 2024 """

import requests
import base64
import re
from collections import namedtuple
from requests.exceptions import RequestException

from homeassistant.exceptions import IntegrationError
from homeassistant.util.json import json_loads

from .const import _LOGGER, ISSUE_URL_ERROR_MESSAGE


# Better storage of PowerOcean endpoint
PowerOceanEndPoint = namedtuple(
    "PowerOceanEndPoint",
    "internal_unique_id, serial, name, friendly_name, value, unit, description, icon",
)


# ecoflow_api to detect device and get device info, fetch the actual data from the PowerOcean device, and parse it
# Rename, there is an official API since june
class Ecoflow:
    """Class representing Ecoflow"""

    def __init__(self, serialnumber, username, password):
        self.sn = serialnumber
        self.unique_id = serialnumber
        self.ecoflow_username = username
        self.ecoflow_password = password
        self.token = None
        self.device = None
        self.session = requests.Session()
        self.url_iot_app = "https://api.ecoflow.com/auth/login"
        self.url_user_fetch = f"https://api-e.ecoflow.com/provider-service/user/device/detail?sn={self.sn}"
        # self.authorize()  # authorize user and get device details

    def get_device(self):
        """Function get device"""
        self.device = {
            "product": "PowerOcean",
            "vendor": "Ecoflow",
            "serial": self.sn,
            "version": "5.1.15",  # TODO: woher bekommt man diese Info?
            "build": "6",  # TODO: wo finde ich das?
            "name": "PowerOcean",
            "features": "Photovoltaik",
        }

        return self.device

    def authorize(self):
        """Function authorize"""
        auth_ok = False  # default
        headers = {"lang": "en_US", "content-type": "application/json"}
        data = {
            "email": self.ecoflow_username,
            "password": base64.b64encode(self.ecoflow_password.encode()).decode(),
            "scene": "IOT_APP",
            "userType": "ECOFLOW",
        }

        try:
            url = self.url_iot_app
            _LOGGER.info("Login to EcoFlow API %s", {url})
            request = requests.post(url, json=data, headers=headers)
            response = self.get_json_response(request)

        except ConnectionError:
            error = f"Unable to connect to {self.url_iot_app}. Device might be offline."
            _LOGGER.warning(error + ISSUE_URL_ERROR_MESSAGE)
            raise IntegrationError(error)

        try:
            self.token = response["data"]["token"]
            self.user_id = response["data"]["user"]["userId"]
            user_name = response["data"]["user"].get("name", "<no user name>")
            auth_ok = True
        except KeyError as key:
            raise Exception(f"Failed to extract key {key} from response: {response}")

        _LOGGER.info("Successfully logged in: %s", {user_name})

        self.get_device()  # collect device info

        return auth_ok

    def get_json_response(self, request):
        """Function get json response"""
        if request.status_code != 200:
            raise Exception(
                f"Got HTTP status code {request.status_code}: {request.text}"
            )
        try:
            response = json_loads(request.text)
            response_message = response["message"]
        except KeyError as key:
            raise Exception(
                f"Failed to extract key {key} from {json_loads(request.text)}"
            )
        except Exception as error:
            raise Exception(f"Failed to parse response: {request.text} Error: {error}")

        if response_message.lower() != "success":
            raise Exception(f"{response_message}")

        return response

    # Fetch the data from the PowerOcean device, which then constitues the Sensors
    def fetch_data(self):
        """Function fetch data from Url."""
        # curl 'https://api-e.ecoflow.com/provider-service/user/device/detail?sn={self.sn}}' \
        # -H 'authorization: Bearer {self.token}'

        url = self.url_user_fetch
        try:
            headers = {"authorization": f"Bearer {self.token}"}
            request = requests.get(self.url_user_fetch, headers=headers, timeout=30)
            response = self.get_json_response(request)

            _LOGGER.debug(f"response_strange___{response}")

            return self._get_sensors(response)

        except ConnectionError:
            error = f"ConnectionError in fetch_data: Unable to connect to {url}. Device might be offline."
            _LOGGER.warning(error + ISSUE_URL_ERROR_MESSAGE)
            raise IntegrationError(error)

        except RequestException as e:
            error = f"RequestException in fetch_data: Error while fetching data from {url}: {e}"
            _LOGGER.warning(error + ISSUE_URL_ERROR_MESSAGE)
            raise IntegrationError(error)

    def __get_unit(self, key):
        """Function get unit from key Name."""
        if key.endswith(("pwr", "Pwr", "Power")):
            unit = "W"
        elif key.endswith(("amp", "Amp")):
            unit = "A"
        elif key.endswith(("soc", "Soc", "soh", "Soh")):
            unit = "%"
        elif key.endswith(("vol", "Vol")):
            unit = "V"
        elif key.endswith(("Watth", "Energy")):
            unit = "Wh"
        elif "Generation" in key:
            unit = "kWh"
        elif key.startswith("bpTemp"):  # TODO: alternative: 'Temp' in key
            unit = "°C"
        else:
            unit = None

        return unit

    def __get_description(self, key):
        # TODO: hier könnte man noch mehr definieren bzw ein translation dict erstellen +1
        # Comment: Ich glaube hier brauchen wir n
        description = key  # default description
        if key == "sysLoadPwr":
            description = "Hausnetz"
        if key == "sysGridPwr":
            description = "Stromnetz"
        if key == "mpptPwr":
            description = "Solarertrag"
        if key == "bpPwr":
            description = "Batterieleistung"
        if key == "bpSoc":
            description = "Ladezustand der Batterie"
        if key == "online":
            description = "Online"
        if key == "systemName":
            description = "System Name"
        if key == "createTime":
            description = "Installations Datum"
        # Battery descriptions
        if key == "bpVol":
            description = "Batteriespannung"
        if key == "bpAmp":
            description = "Batteriestrom"
        if key == "bpCycles":
            description = "Ladezyklen"
        if key == "bpTemp":
            description = "Temperatur der Batteriezellen"

        return description

    def _get_sensors(self, response):
        # get master and slave serial numbers from from response['data']
        serials = self._get_serial_numbers(response)

        if serials == 0 :
        elif serials == 2:
            

            _LOGGER.debug(f"serial_numbers__{serials}")
            _LOGGER.debug(f"master_serial_number__{self.master_sn}")
            _LOGGER.debug(f"master_data__{self.master_data}")

        
        
            # get sensors from response['data']

            # _LOGGER.debug(f"sensors_init__{sensors}")
        
            sensors = self.__get_sensors_data(response)

            _LOGGER.debug(f"sensors_data__{sensors}")

            # get sensors from 'JTS1_ENERGY_STREAM_REPORT'
            # sensors = self.__get_sensors_energy_stream(response, sensors)  # is currently not in use

            # get sensors from 'JTS1_EMS_CHANGE_REPORT'
            # siehe parameter_selected.json    #  get bpSoc from ems_change

            _LOGGER.debug(f"sensors_in__{sensors}")

        
            inverter_data = self.master_data
            inverter_sn = self.master_sn
        
            sensors = self._get_sensors_ems_change(inverter_data, inverter_sn, "_master", sensors)
            sensors = self._get_sensors_battery(inverter_data, inverter_sn, "_master", sensors)
            sensors = self._get_sensors_ems_heartbeat(inverter_data, inverter_sn, "_master", sensors)

        _LOGGER.debug(f"sensors_back__{sensors}")

            inverter_data = self.slave_data
            inverter_sn = self.slave_sn
            
            sensors = self._get_sensors_ems_change(inverter_data, inverter_sn, "_slave", sensors)
            sensors = self._get_sensors_battery(inverter_data, inverter_sn, "_slave", sensors)
            sensors = self._get_sensors_ems_heartbeat(inverter_data, inverter_sn, "_slave", sensors)
            
            _LOGGER.debug(f"sensors_back2__{sensors}")
    
            # get info from batteries  => JTS1_BP_STA_REPORT
           
    
            # get info from PV strings  => JTS1_EMS_HEARTBEAT
    
    
            return sensors
        else
            _LOGGER.debug(f"more than two inverters aborting")
        return

    def __get_sensors_data(self, response):
        d = response["data"].copy()

        # sensors not in use: note, bpSoc is taken from the EMS CHANGE report
        # [ 'bpSoc', 'sysBatChgUpLimit', 'sysBatDsgDownLimit','sysGridSta', 'sysOnOffMachineStat',
        #   'location', 'timezone', 'quota']

        sens_select = [
            "sysLoadPwr",
            "sysGridPwr",
            "mpptPwr",
            "bpPwr",
            "online",
            "todayElectricityGeneration",
            "monthElectricityGeneration",
            "yearElectricityGeneration",
            "totalElectricityGeneration",
            "systemName",
            "createTime",
        ]

        sensors = dict()  # start with empty dict
        for key, value in d.items():
            if key in sens_select:  # use only sensors in sens_select
                if not isinstance(value, dict):
                    # default uid, unit and descript
                    unique_id = f"{self.sn}_{key}"
                    special_icon = None
                    if key == "mpptPwr":
                        special_icon = "mdi:solar-power"

                    sensors[unique_id] = PowerOceanEndPoint(
                        internal_unique_id=unique_id,
                        serial=self.sn,
                        name=f"{self.sn}_{key}",
                        friendly_name=key,
                        value=value,
                        unit=self.__get_unit(key),
                        description=self.__get_description(key),
                        icon=special_icon,
                    )

        return sensors
        
    def _get_serial_numbers(self, response):
      
        p = response["data"]["parallel"]
        _LOGGER.debug(f"parralel_present__{len(p)}")

        if len(p) = 0 :
            return 0
        

        keys_2 = p.keys()
        _LOGGER.debug(f"serial_p_keys2__{keys_2}")
    
        for key in p.keys():
            pp = response["data"]["parallel"][key]
            keys_3 = pp.keys()
            _LOGGER.debug(f"serial_pp_keys___{keys_3}")

        self.slave_sn = next(iter(keys_2))
        self.master_sn = next(reversed(keys_2))

        self.master_data = response["data"]["parallel"][self.master_sn]
        self.slave_data = response["data"]["parallel"][self.slave_sn]
        
        return len(p)


    


    # Note, this report is currently not in use. Sensors are taken from response['data']
    # def __get_sensors_energy_stream(self, response, sensors):
    #     report = "JTS1_ENERGY_STREAM_REPORT"
    #     d = response["data"]["quota"][report]
    #     prefix = (
    #         "_".join(report.split("_")[1:3]).lower() + "_"
    #     )  # used to construct sensor name
    #
    #     # sens_all = ['bpSoc', 'mpptPwr', 'updateTime', 'bpPwr', 'sysLoadPwr', 'sysGridPwr']
    #     sens_select = d.keys()
    #     data = {}
    #     for key, value in d.items():
    #         if key in sens_select:  # use only sensors in sens_select
    #             # default uid, unit and descript
    #             unique_id = f"{self.sn}_{report}_{key}"
    #
    #             data[unique_id] = PowerOceanEndPoint(
    #                 internal_unique_id=unique_id,
    #                 serial=self.sn,
    #                 name=f"{self.sn}_{prefix+key}",
    #                 friendly_name=prefix + key,
    #                 value=value,
    #                 unit=self.__get_unit(key),
    #                 description=self.__get_description(key),
    #                 icon=None,
    #             )
    #     dict.update(sensors, data)
    #
    #     return sensors

    def _get_sensors_ems_change(self, inverter_data, inverter_sn, inverter_string, sensors):
        report = "JTS1_EMS_CHANGE_REPORT"
        d = inverter_data[report]

        sens_select = [
            "bpTotalChgEnergy",
            "bpTotalDsgEnergy",
            "bpSoc",
            "bpOnlineSum",  # number of batteries
            "emsCtrlLedBright",
        ]

        # add mppt Warning/Fault Codes
        keys = d.keys()
        
        r = re.compile("mppt.*Code")
        wfc = list(filter(r.match, keys))  # warning/fault code keys
        sens_select += wfc

       
        
        data = {}
        for key, value in d.items():
            if key in sens_select:  # use only sensors in sens_select
                # default uid, unit and descript
                unique_id = f"{inverter_sn}_{report}_{key}{inverter_string}"

                data[unique_id] = PowerOceanEndPoint(
                    internal_unique_id=unique_id,
                    serial=inverter_sn,
                    name=f"{inverter_sn}_{key}{inverter_string}",
                    friendly_name = key + inverter_string,
                    value=value,
                    unit=self.__get_unit(key),
                    description=self.__get_description(key),
                    icon=None,
                )
        dict.update(sensors, data)

        return sensors

    def _get_sensors_battery(self, inverter_data, inverter_sn, inverter_string, sensors):
        report = "JTS1_BP_STA_REPORT"
        d = inverter_data[report]
        keys = list(d.keys())
        
        _LOGGER.debug(f"inverter__{inverter_sn}")
        _LOGGER.debug(f"batt_keys__{keys}")
 
        # loop over N batteries:
        batts = [s for s in keys if len(s) > 12]

        _LOGGER.debug(f"batts__{batts}")
 
        bat_sens_select = [
            "bpPwr",
            "bpSoc",
            "bpSoh",
            "bpVol",
            "bpAmp",
            "bpCycles",
            "bpSysState",
            "bpRemainWatth",
            "bpTemp",
        ]

        data = {}
        prefix = "_bpack"
        _LOGGER.debug(f"batts_no__{enumerate(batts)}")

        for ibat, bat in enumerate(batts):
            name = prefix + "%i_" % (ibat + 1)
            _LOGGER.debug(f"batty__{ibat}{bat}")
            _LOGGER.debug(f"batts_name__{name}")
            d_bat = json_loads(d[bat])
            _LOGGER.debug(f"batts_dbat__{d_bat}")

            for key, value in d_bat.items():
                _LOGGER.debug(f"batts_dbat_items__{d_bat.items}")
                if key in bat_sens_select:
                    # default uid, unit and descript
                    unique_id = f"{inverter_sn}_{report}_{bat}_{key}"
                    description_tmp = f"{name}" + self.__get_description(key)
                    special_icon = None
                    if key == "bpAmp":
                        special_icon = "mdi:current-dc"
                    if key == "bpTemp":
                        temp = d_bat[key]
                        value = sum(temp) / len(temp)
                        _LOGGER.debug(f"batts_temps__{temp}")
                        _LOGGER.debug(f"batts_avg_temp__{value}")
                    data[unique_id] = PowerOceanEndPoint(
                        internal_unique_id=unique_id,
                        serial=inverter_sn,
                        name=f"{inverter_sn}_{key}",
                        friendly_name= inverter_string + name + key,

                        value=value,
                        unit=self.__get_unit(key),
                        description=description_tmp,
                        icon=special_icon,
                    )
            # compute mean temperature of cells
     #       key = "bpTemp"
     #       temp = d_bat[key]
     #       value = sum(temp) / len(temp)
     #       unique_id = f"{inverter_sn}_{report}_{bat}_{key}"
     #       description_tmp = f"{name}" + self.__get_description(key)
     #       _LOGGER.debug(f"batts_description_tmp__{description_tmp}")
     #       data[unique_id] = PowerOceanEndPoint(
     #           internal_unique_id=unique_id,
     #           serial=inverter_sn,
     #           name=f"{inverter_sn}_{name + key}",
     #           friendly_name = inverter_string + name + key,
     #           value=value,
     #           unit=self.__get_unit(key),
     #           description=description_tmp,
     #           icon=None,
     #       )

        dict.update(sensors, data)

        return sensors

    def _get_sensors_ems_heartbeat(self, inverter_data, inverter_sn, inverter_string, sensors):
        report = "JTS1_EMS_HEARTBEAT"
        d = inverter_data[report]
        # sens_select = d.keys()  # 68 Felder
        sens_select = [
            "bpRemainWatth",
            "emsBpAliveNum",
            "emsBpPower",
            "pcsActPwr",
            "pcsMeterPower",

        ]
        data = {}
        for key, value in d.items():
            if key in sens_select:
                # default uid, unit and descript
                unique_id = f"{inverter_sn}_{report}_{key}_{inverter_string}"
                description_tmp = self.__get_description(key)
                data[unique_id] = PowerOceanEndPoint(
                    internal_unique_id=unique_id,
                    serial=inverter_sn,
                    name=f"{inverter_sn}_{key}_{inverter_string}",
                    friendly_name= key + "_" + inverter_string,
                    value=value,
                    unit=self.__get_unit(key),
                    description=description_tmp,
                    icon=None,
                )

        # special for phases
        phases = ["pcsAPhase", "pcsBPhase", "pcsCPhase"]
        for i, phase in enumerate(phases):
            for key, value in d[phase].items():
                name = phase + "_" + key +  "_" + inverter_string
                unique_id = f"{inverter_sn}_{report}_{name}_{inverter_string}"

                data[unique_id] = PowerOceanEndPoint(
                    internal_unique_id=unique_id,
                    serial=inverter_sn,
                    name=f"{inverter_sn}_{name}_{inverter_string}",
                    friendly_name=f"{name}_{inverter_string}",
                    value=value,
                    unit=self.__get_unit(key),
                    description=self.__get_description(key),
                    icon=None,
                )

        # special for mpptPv
        n_strings = len(d["mpptHeartBeat"][0]["mpptPv"])  # TODO: auch als Sensor?
        mpptpvs = []
        for i in range(1, n_strings + 1):
            mpptpvs.append(f"mpptPv{i}")
        mpptPv_sum = 0.0
        for i, mpptpv in enumerate(mpptpvs):
            for key, value in d["mpptHeartBeat"][0]["mpptPv"][i].items():
                unique_id = f"{inverter_sn}_{report}_mpptHeartBeat_{mpptpv}_{key}"
                special_icon = None
                if key.endswith("amp"):
                    special_icon = "mdi:current-dc"
                if key.endswith("pwr"):
                    special_icon = "mdi:solar-power"

                data[unique_id] = PowerOceanEndPoint(
                    internal_unique_id=unique_id,
                    serial=inverter_sn,
                    name=f"{inverter_sn}_{mpptpv}_{key}_{inverter_string}",
                    friendly_name=f"{mpptpv}_{key}_{inverter_string}",
                    value=value,
                    unit=self.__get_unit(key),
                    description=self.__get_description(key),
                    icon=special_icon,
                )
                # sum power of all strings
                if key == "pwr":
                    mpptPv_sum += value

        # create total power sensor of all strings
        name = "mpptPv_pwrTotal"
        unique_id = f"{inverter_sn}_{report}_mpptHeartBeat_{name}"

        data[unique_id] = PowerOceanEndPoint(
            internal_unique_id=unique_id,
            serial=inverter_sn,
            name=f"{inverter_sn}_{name}_{inverter_string}",
            friendly_name=f"{name}_{inverter_string}",
            value=mpptPv_sum,
            unit=self.__get_unit(key),
            description="Solarertrag aller Strings",
            icon="mdi:solar-power",
        )

        dict.update(sensors, data)

        return sensors


class AuthenticationFailed(Exception):
    """Exception to indicate authentication failure."""
