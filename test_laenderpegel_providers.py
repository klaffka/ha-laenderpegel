import json
from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.laenderpegel.models import GaugeStation
from custom_components.laenderpegel.providers import bb, bw, by, hb, he, mv, ni, nw, rp, sh, sl, sn, st, th
from custom_components.laenderpegel.providers.wiski import parse_wiski_data

BERLIN = ZoneInfo("Europe/Berlin")


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    async def read(self):
        if isinstance(self._payload, bytes):
            return self._payload
        if isinstance(self._payload, str):
            return self._payload.encode("utf-8")
        return json.dumps(self._payload).encode()

    async def json(self):
        if isinstance(self._payload, (dict, list)):
            return self._payload
        return json.loads(self._payload)

    async def text(self):
        if isinstance(self._payload, str):
            return self._payload
        return json.dumps(self._payload)


class FakeContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, handlers):
        self._handlers = handlers

    def get(self, url, **kwargs):
        for key, payload in self._handlers.items():
            if key in url:
                return FakeContext(FakeResponse(payload))
        raise AssertionError(f"Unerwartete URL: {url}")


BB_START_PHP = """
var f = new L.FeatureGroup();
f.addLayer(new L.Marker([51.9, 13.5])).on('click', function() {
  showInfo({
    pkz: '6650100',
    name: 'Zschorno',
    gewaesser: 'Foehrenfliess',
    datum: '23.08.2026',
    zeit: '17:15',
    klasse: '1',
    wert: '76'
  });
});
/* PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING
   PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING_PADDING */
f.addLayer(new L.Marker([52.1, 13.6])).on('click', function() {
  showInfo({
    pkz: '6650200',
    name: 'Testpegel',
    gewaesser: 'Foehrenfliess',
    datum: '23.08.2026',
    zeit: '17:15',
    klasse: '3',
    wert: '320'
  });
});
"""

BB_CSV = (
    'Datum;"Wasserstand in cm";"Stationsnummer: 6650100"\r\n'
    '"23.08.2026 17:00";75\r\n'
    '"23.08.2026 17:15";76\r\n'
    '"23.08.2026 17:30";-777\r\n'
    '"23.08.2026 17:45";78.5\r\n'
)


async def test_bb_parser():
    provider = bb.Provider()
    session = FakeSession({"/start.php": BB_START_PHP, "_wasserstand.csv": BB_CSV})
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="6650100", name="Zschorno", wasser="Foehrenfliess", stand="23.08.2026 17:15", wert="76"),
        GaugeStation(
            id="6650200",
            name="Testpegel",
            wasser="Foehrenfliess",
            stand="23.08.2026 17:15",
            wert="320",
            warnstufe="Meldestufe 2",
            warnstufe_aktiv=True,
        ),
    ]
    punkte = await provider.async_get_series(session, "6650100")
    assert [wert for _, wert in punkte] == [75.0, 76.0, 78.5]
    assert punkte[0][0] == datetime(2026, 8, 23, 17, 0, tzinfo=BERLIN)


MV_LIST_HTML = """
<table>
<tr><td>Kladrum</td><td>Warnow</td><td>23.08.2026 07:00</td><td>15</td></tr>
<tr><td><a href='04416.1.html'>Kladrum</a></td><td>Warnow</td><td>23.08.2026 07:00</td><td>15</td></tr>
</table>
"""

MV_DATA_JS = """
var daten = [
new Date('2026/08/23 06:45'), 14.5,
new Date('2026/08/23 07:00'), 15,
];
"""

MV_DETAIL_HTML = "<html>PNP = 0 m</html>"


async def test_mv_parser():
    provider = mv.Provider()
    session = FakeSession(
        {
            "pegel_list.html": MV_LIST_HTML,
            "/data/04416.1.js": MV_DATA_JS,
            "/04416.1.html": MV_DETAIL_HTML,
        }
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="04416.1", name="Kladrum", wasser="Warnow", stand="23.08.2026 07:00", wert="15")
    ]
    punkte = await provider.async_get_series(session, "04416.1")
    assert [wert for _, wert in punkte] == [14.5, 15.0]
    assert await provider.async_get_gauge_zero(session, "04416.1") == 0.0


SH_STAMM = (
    "sta_name_s;sta_no_s;wto_name_s;a;b;c;pnp_fl;d;e;aufgelassen_ts\n"
    "Ostorfer See;4243000;Ostorfer See;x;y;z;-5,0;a;b;\n"
    "Altpegel;4001000;Alte Notte;x;y;z;1,2;a;b;01.01.2020 00:00:00\n"
)

SH_LIVE = "#Date;Data\n2026-08-23 21:40,581\nNULL\n2026-08-23 21:55,582\n"


async def test_sh_parser():
    provider = sh.Provider()
    session = FakeSession(
        {"pegel_stammdaten.csv": SH_STAMM, "/hsidata/4243000W.txt": SH_LIVE}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [GaugeStation(id="4243000", name="Ostorfer See", wasser="Ostorfer See")]
    punkte = await provider.async_get_series(session, "4243000")
    assert [wert for _, wert in punkte] == [581.0, 582.0]
    assert await provider.async_get_gauge_zero(session, "4243000") == -5.0


SL_DATEN_JS = (
    "Pegel(387,456,'1464130','6','Wittringen','Saar','  62','23.08.2026 21:45','   0');\n"
    "Pegel(388,457,'1464140','6','Losheim','Saar','****','23.08.2026 21:45','   0');\n"
)


async def test_sl_parser():
    provider = sl.Provider()
    session = FakeSession({"Daten.js": SL_DATEN_JS})
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="1464130", name="Wittringen", wasser="Saar", stand="23.08.2026 21:45", wert="62"),
        GaugeStation(id="1464140", name="Losheim", wasser="Saar", stand="23.08.2026 21:45", wert=""),
    ]
    punkte = await provider.async_get_series(session, "1464130")
    assert punkte == [(datetime(2026, 8, 23, 21, 45, tzinfo=BERLIN), 62.0)]
    assert await provider.async_get_series(session, "1464140") == []


ST_STATIONS = [
    {
        "station_no": "440004",
        "station_name": "Alleringersleben",
        "catchment_name": "Pegel 440004 Alleringersleben (Weser, Aller)",
        "GAUGE_DATUM": "113.237",
    },
    {
        "station_no": "591043",
        "station_name": "Mehringen",
        "catchment_name": "Pegel 591043 Mehringen (Elbe)",
        "GAUGE_DATUM": "",
    },
]

ST_WEEK = [
    {
        "station_no": "440004",
        "ts_unitsymbol": "cm",
        "data": [
            ["2026-08-17T00:00:00.000+02:00", 10],
            ["2026-08-17T00:15:00.000+02:00", 11.5],
        ],
    }
]


async def test_st_parser():
    provider = st.Provider()
    session = FakeSession(
        {"stations.json": ST_STATIONS, "/W/week.json": ST_WEEK}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="440004", name="Alleringersleben", wasser="Weser"),
        GaugeStation(id="591043", name="Mehringen", wasser="Elbe"),
    ]
    punkte = await provider.async_get_series(session, "440004")
    assert [wert for _, wert in punkte] == [10.0, 11.5]
    assert await provider.async_get_gauge_zero(session, "440004") == 113.237
    assert await provider.async_get_gauge_zero(session, "591043") is None


HE_STATIONS = [
    {
        "station_id": "42482",
        "station_no": "25842500",
        "station_name": "Asslar",
        "catchment_name": "Dill",
        "object_type": "Allgemein;Oberflächengewässer",
        "GAUGE_DATUM": "153.03",
    },
    {
        "station_id": "41145",
        "station_no": "12345678",
        "station_name": "AuhammerN",
        "catchment_name": "Eder",
        "object_type": "Allgemein;Klimastation;Niederschlag",
        "GAUGE_DATUM": "",
    },
]

HE_SERIES = [
    {
        "ts_unitsymbol": "cm",
        "data": [
            ["2026-08-23T22:30:00.000+02:00", 36],
            ["2026-08-23T22:45:00.000+02:00", 37],
        ],
    }
]


async def test_he_parser():
    provider = he.Provider()
    session = FakeSession(
        {"stations.json": HE_STATIONS, "AktuelleDaten48h.json": HE_SERIES}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [GaugeStation(id="25842500", name="Asslar", wasser="Dill")]
    punkte = await provider.async_get_series(session, "25842500")
    assert [wert for _, wert in punkte] == [36.0, 37.0]
    assert await provider.async_get_gauge_zero(session, "25842500") == 153.03


NW_LAYER = [
    {
        "station_id": "28621",
        "station_no": "4667100000100",
        "site_no": "100",
        "station_name": "Oberahle",
        "catchment_name": "Rureinzugsgebiet",
        "timestamp": "2026-08-23T22:45:00.000+01:00",
        "ts_value": "15.00",
        "ts_unitsymbol": "cm",
    },
    {
        "station_id": "28498",
        "station_no": "2825320000100",
        "site_no": "100",
        "station_name": "Kirchberg2",
        "catchment_name": "Rureinzugsgebiet",
        "timestamp": "2026-06-12T10:30:00.000+01:00",
        "ts_value": None,
        "ts_unitsymbol": "cm",
    },
]

NW_WEEK = [
    {
        "station_no": "4667100000100",
        "ts_unitsymbol": "cm",
        "data": [
            ["2026-08-17T00:00:00.000+01:00", 15.3],
            ["2026-08-17T00:15:00.000+01:00", 15.0],
        ],
    }
]


async def test_nw_parser():
    provider = nw.Provider()
    session = FakeSession(
        {"layers/10/index.json": NW_LAYER, "/S/week.json": NW_WEEK}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen[0] == GaugeStation(
        id="4667100000100", name="Oberahle", wasser="Rureinzugsgebiet", stand="22:45", wert="15.00"
    )
    assert stationen[1].wert == ""
    punkte = await provider.async_get_series(session, "4667100000100")
    assert [wert for _, wert in punkte] == [15.3, 15.0]


RP_CONFIG = {
    "rivers": {"2718000000": {"name": "Ahr"}},
    "measurementsite": {
        "26600128": {
            "name": "Kronenburger See",
            "number": "26600128",
            "rivers": ["2718000000"],
            "elevation": 489.8,
        }
    },
}

RP_INDEX = {
    "measurementSites": {
        "26600128": {
            "xLast": "2026-08-23T21:45:00Z",
            "yLast": 483.54,
            "measurements": [{"x": "2026-08-23T21:30:00Z", "y": 483.53}],
        }
    }
}

RP_MEASUREMENT_SITE = {
    "W": {
        "xLast": "2026-08-23T21:45:00Z",
        "yLast": 483.54,
        "measurements": [
            {"x": "2026-08-21T21:45:00Z", "y": 483.53},
            {"x": "2026-08-23T21:45:00Z", "y": 483.54},
        ],
    }
}


async def test_rp_parser():
    provider = rp.Provider()
    session = FakeSession(
        {
            "/config": RP_CONFIG,
            "/index": RP_INDEX,
            "measurement-site/26600128": RP_MEASUREMENT_SITE,
        }
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(
            id="26600128",
            name="Kronenburger See",
            wasser="Ahr",
            stand="21:45",
            wert="483.54",
        )
    ]
    punkte = await provider.async_get_series(session, "26600128")
    assert [wert for _, wert in punkte] == [483.53, 483.54]
    assert await provider.async_get_gauge_zero(session, "26600128") == 489.8


NI_STAMMDATEN = {
    "getStammdatenResult": [
        {
            "STA_ID": 486,
            "Name": "Poppenburg",
            "Ort": "Keine Daten",
            "GewaesserName": "Leine",
        },
        {
            "STA_ID": 500,
            "Name": "Haste",
            "Ort": "Haste",
            "GewaesserName": "Leine",
        },
    ]
}

NI_CHART = {
    "getPegelDatenspurenChartResult": [
        {
            "IstVorhersage": False,
            "PegelHoehe": 68.46,
            "Pegelstaende": [
                {"DatumUTC": "/Date(1787522400000)/", "Wert": 83},
                {"DatumUTC": "/Date(1787526000000)/", "Wert": 84},
                {"DatumUTC": None, "Wert": 99},
            ],
        },
        {
            "IstVorhersage": True,
            "Pegelstaende": [{"DatumUTC": "/Date(1787600000000)/", "Wert": 120}],
        },
    ]
}


async def test_ni_parser():
    provider = ni.Provider()
    session = FakeSession(
        {"stammdaten/stationen/All": NI_STAMMDATEN, "datenspuren": NI_CHART}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="486", name="Poppenburg", wasser="Leine"),
        GaugeStation(id="500", name="Haste (Haste)", wasser="Leine"),
    ]
    punkte = await provider.async_get_series(session, "486")
    assert [wert for _, wert in punkte] == [83.0, 84.0]
    assert punkte[0][0] == datetime(2026, 8, 24, 0, 0, tzinfo=BERLIN)
    assert await provider.async_get_gauge_zero(session, "486") == 68.46


BY_LIST_HTML = """
<table>
<tr><th>Messstelle</th><th>Gew&auml;sser</th><th>Lkr.</th><th>Datum</th><th>Wasserstand [cm]</th></tr>
<tr>
  <td><a href="https://www.gkd.bayern.de/de/fluesse/wasserstand/kelheim/muenchen-16005701/messwerte?method=tabellen">München</a></td>
  <td>Isar</td>
  <td>M</td>
  <td>24.08.2026 00:15 Uhr</td>
  <td>89</td>
</tr>
</table>
"""

BY_TABELLE = """
<table>
<tr><th>Datum</th><th>Wasserstand [cm]</th></tr>
<tr><td>24.08.2026 00:15 Uhr</td><td>89</td></tr>
<tr><td>23.08.2026 23:45 Uhr</td><td>90</td></tr>
<tr><td>n. v.</td><td>-</td></tr>
</table>
"""


async def test_by_parser():
    provider = by.Provider()
    session = FakeSession(
        {
            "/wasserstand/tabellen": BY_LIST_HTML,
            "messwerte/tabelle": BY_TABELLE,
        }
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="16005701", name="München", wasser="Isar", stand="00:15", wert="89")
    ]
    punkte = await provider.async_get_series(session, "16005701")
    assert [wert for _, wert in punkte] == [90.0, 89.0]
    assert punkte[0][0] == datetime(2026, 8, 23, 23, 45, tzinfo=BERLIN)


TH_PORTAL = """
<table>
<tr><th>Status</th><th>Pegelkennz.</th><th>Pegel</th><th>Gewässer</th><th>Betreiber</th><th>Info</th><th>Prog.</th><th>HWMP</th><th>DatumUhrzeit</th><th>Wasserstand</th><th>Durchfluss</th><th>Tendenz</th><th>Ganglinie</th><th>Jahres-MQ</th></tr>
<tr><td></td><td>25168.0</td><td>Autenhausen</td><td>Kreck</td><td>WWA Kronach</td><td></td><td></td><td></td><td>23.08.2026 23:45</td><td>119</td><td>(-)</td><td>0,135</td><td>(-)</td><td></td><td>1,04</td></tr>
<tr><td></td><td>42000.1</td><td>Eisfeld Bahnbrücke</td><td>Werra</td><td>TLUBN</td><td></td><td></td><td>2</td><td>23.08.2026 23:45</td><td>520</td><td>(-)</td><td>0,613</td><td>(-)</td><td></td><td>2,81</td></tr>
</table>
"""


async def test_th_parser():
    provider = th.Provider()
    session = FakeSession({"thueringen.html": TH_PORTAL})
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="251680", name="Autenhausen", wasser="Kreck", stand="23:45", wert="119"),
        GaugeStation(
            id="420001",
            name="Eisfeld Bahnbrücke",
            wasser="Werra",
            stand="23:45",
            wert="520",
            warnstufe="Meldestufe 2",
            warnstufe_aktiv=True,
        ),
    ]
    punkte = await provider.async_get_series(session, "251680")
    assert punkte == [(datetime(2026, 8, 23, 23, 45, tzinfo=BERLIN), 119.0)]
    assert await provider.async_get_series(session, "999999") == []


SN_UBERSICHT = """
<div class="popUp popUpMs">
  <div class="popUpStatus"><div>Kein Hochwasser</div></div>
  <div class="popUpTitle"><span class="popUpTitleBold">Schöna / Elbe</span></div>
  <div class="clearfix">
    <div class="popUpMsDiagrammContainer">
      <div class="popUpMsDiagramm" style="background-image: url('/umwelt/infosysteme/hwims/portal/diagramme/diagrammimage_501010_INFOBOXWEB_W');"></div>
    </div>
    <div class="popUpMsTableContainer">
      <div class="popUpRow">
        <span class="popUpLabel">Datum:</span>
        <span class="popUpValue">24.08.2026<br />00:15<span> </span>Uhr</span>
      </div>
      <div class="popUpRow">
        <span class="popUpLabel">Wasserstand:</span>
        <span class="popUpValue">111<span> </span>cm</span>
      </div>
    </div>
  </div>
  <div class="popUpMsTendenz"><div class="popUpRow"></div></div>
</div>
<a href="wasserstand-pegel-501010" class="msWrapper pegel msIcon"></a>
"""

SN_DETAIL = """
<table>
<tr><th>Zeitpunkt</th><th>W</th><th>Q</th></tr>
<tr><td>24.08.2026 00:15</td><td>111</td><td>132</td></tr>
<tr><td>24.08.2026 00:30</td><td>112</td><td>135</td></tr>
<tr><td>31.12.2099 00:00</td><td>999</td><td>999</td></tr>
</table>
"""


async def test_sn_parser():
    provider = sn.Provider()
    session = FakeSession(
        {"wasserstand-uebersicht": SN_UBERSICHT, "wasserstand-pegel-501010": SN_DETAIL}
    )
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(
            id="501010", name="Schöna", wasser="Elbe", stand="00:15", wert="111", warnstufe="keine"
        )
    ]
    assert await provider.async_get_station(session, "501010") is not None
    punkte = await provider.async_get_series(session, "501010")
    assert [wert for _, wert in punkte] == [111.0, 112.0]


HB_LIST = """
<table id="pegeltabelle">
<tr><th>Gewässer</th><th>Pegel</th><th>Wasserstand</th><th>Trend</th><th>Warnstufe</th><th>Menge</th><th>Datum</th><th>Warnstufe</th></tr>
<tr>
  <td itemscope><b class='remove-me'>Gewässer</b><span itemprop='name'>Ammersbek</span></td>
  <td class='ganglinie popups icon imgicon left'><b class='remove-me'>Pegel</b>
    <button class='pegelbuttonlink p99003' data-modal='grafik-99003.html'
      data-modalTitle='Details zum Pegel Brügkamp - 99003' id='modal_99003_lnk'>
    </button>
    <b class='remove-me'>Wasserstand W&nbsp;[NHN&nbsp;&plusmn;&nbsp;cm]</b><span itemprop='value'>2.071</span></td>
  <td>Datum / Uhrzeit 23.08.26 19:00</td>
  <td>Trend gleich</td><td class='warn-0 ' data-text='0'><b class='remove-me ui-table-cell-label'>Warnstufe</b><span role='img' alt='' class='cssicon cssicon--circle pi_0'></span>keine</td>
  <td>Menge 1.0 mm / 24 Std.</td>
  <td>Datum / Uhrzeit 24.08.26 00:10</td>
  <td class='warn-0 ' data-text='0'><b class='remove-me ui-table-cell-label'>Warnstufe</b><span role='img' alt='' class='cssicon cssicon--circle pi_0'></span>keine</td>
</tr>
</table>
"""


async def test_hb_parser():
    provider = hb.Provider()
    session = FakeSession({"pegel.html": HB_LIST})
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="99003", name="Brügkamp", wasser="Ammersbek", stand="19:00", wert="2.071")
    ]
    punkte = await provider.async_get_series(session, "99003")
    assert punkte == [(datetime(2026, 8, 23, 19, 0, tzinfo=BERLIN), 2.071)]


BW_MAP = """
<script>
var SiteStations = [
['00436',3477197.344,5461690.674,'Wiesloch-Nord','Waldangelbach','','15','cm','','24.08.2026 00:00 MESZ','0.11','m³/s','','24.08.2026 00:00 MESZ',0,'0',0,'00436-140',5,0,0,0,0],
['09055',3548465,5249617,'Diepoldsau','Alpenrhein','','--','','','--','114','m³/s','-20.0','23.08.2026 23:50 MESZ',0,'7',0,'09055-340',5,0,0,0,7]
];
</script>
"""


async def test_bw_parser():
    provider = bw.Provider()
    session = FakeSession({"map_peg.html": BW_MAP})
    stationen = await provider.async_get_stations(session)
    assert stationen == [
        GaugeStation(id="00436", name="Wiesloch-Nord", wasser="Waldangelbach", stand="00:00", wert="15.0"),
        GaugeStation(id="09055", name="Diepoldsau", wasser="Alpenrhein", stand="", wert=""),
    ]
    punkte = await provider.async_get_series(session, "00436")
    assert punkte == [(datetime(2026, 8, 24, 0, 0, tzinfo=BERLIN), 15.0)]
    assert await provider.async_get_series(session, "09055") == []


def test_parse_wiski_data():
    punkte = parse_wiski_data(
        [{"data": [["2026-08-17T00:00:00.000+02:00", 10], ["2026-08-17T00:15:00.000+02:00", None]]}]
    )
    assert punkte == [(datetime(2026, 8, 17, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")), 10.0)]