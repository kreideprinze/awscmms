"""First-startup seeding: full Appendix A hierarchy, users, failure modes, error codes,
PM templates, runtime templates, reliability settings, notification templates,
spare locations, starter spares inventory, machine-spare recommendations.
The system must NEVER start empty."""
import logging
import os
import uuid
from datetime import datetime, timezone

from auth import hash_password
from database import db

logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def nid():
    return str(uuid.uuid4())


# ---------------- Appendix A: exact machine hierarchy ----------------
APPENDIX_A = {
    'PC21': {
        'Potato Receiving': ['Crate Dumper', 'Hopper Feeder Conveyor', 'Potato Transfer Conveyor 1', 'Potato Transfer Conveyor 2', 'Potato Transfer Conveyor 3', 'Potato Transfer Conveyor 4', 'Potato Transfer Conveyor 5', 'Potato Transfer Conveyor 6'],
        'Peeling': ['Vertical Screw', 'Continuous Peeler 1', 'Continuous Peeler 2'],
        'Trim & Pare': ['Trim & Pare Infeed Conveyor', 'Trim & Pare Conveyor'],
        'Slicing': ['Slicer Infeed Inclined Conveyor', 'Slicer Auger', 'Slicer 1', 'Slicer 2'],
        'Washing': ['Drum Washer', 'Pre Washer Conveyor', 'Speed Washer Conveyor', 'Air Knife', 'Air Sweep'],
        'Frying': ['Fryer', 'Main Oil Pump', 'Oil Management System', 'Heat Exchanger (CNG)', 'Heat Exchanger (Steam)', 'Fryer Catch Box'],
        'Optical Sorting': ['MM55 FL710 Conveyor', 'Optyx Infeed Vibratory Conveyor', 'Optyx', 'Optyx Rejection Conveyor'],
        'Seasoning': ['Seasoning Infeed Z Conveyor', 'Vibratory Conveyor', 'Weighing Conveyor', 'Bulk Feeder', 'Rospen Hopper', 'Scarf Plate', 'Seasoning Tumbler', 'Gooseneck Conveyor'],
        'Waste Handling': ['Crusher Unit', 'Dust Collector', 'Drum Washer Catch Box', 'Speed Washer Catch Box', 'Slicer Crusher Unit'],
    },
    'PC32': {
        'Receiving': ['Crate Dumper', 'Potato Transfer Conveyor 1', 'Potato Transfer Conveyor 2'],
        'Washing': ['Barrel Washer', 'Barrel Washer Infeed Conveyor', 'Dip Washer Unit', 'Dip Washer Conveyor', 'Hydrocyclone'],
        'Peeling': ['Peeler 1', 'Peeler 2', 'Peeler 3', 'Peeler 4', 'Peeler Infeed Conveyor', 'Peeler Infeed Vibratory Conveyor', 'Peeler Outfeed Vibratory Conveyor', 'Peeler Outfeed Inclined Conveyor'],
        'Cutting': ['Auto Halver', 'Slicer Landing Conveyor', 'Slicer Infeed Inclined Conveyor', 'Slicer 1', 'Slicer 2', 'Slicer 3', 'Slicer 4'],
        'Trim & Pare': ['Trim & Pare Conveyor'],
        'Frying': ['Fryer', 'Main Oil Pump', 'Oil Management System', 'Heat Exchanger CNG', 'Heat Exchanger Steam', 'Fryer Catch Box'],
        'Optical Sorting': ['Optyx', 'Optyx Infeed Vibratory Conveyor', 'Recycle Conveyor', 'Recycle Vibratory', 'Rejection Conveyor', 'Optyx Outfeed Vibratory Conveyor'],
        'Seasoning': ['Seasoning Infeed Conveyor', 'Vibratory Conveyor', 'Weighing Infeed Conveyor', 'Bulk Feeder', 'Rospen Hopper', 'Scarf Plate', 'Seasoning Tumbler', 'Dust Collector', 'Gooseneck Conveyor'],
    },
    'PC36': {
        'Receiving': ['Crate Dumper', 'Potato Transfer Conveyor'],
        'Peeling': ['Peeler 1', 'Peeler 2', 'Peeler 3', 'Peeler 4', 'Peeler Infeed Conveyor', 'Peeler Infeed Vibratory Conveyor', 'Peeler Outfeed Conveyor', 'Peeler Outfeed Vibratory Conveyor'],
        'Trim & Pare': ['Trim & Pare Infeed Conveyor', 'Trim & Pare Conveyor'],
        'Slicing': ['Slicer Infeed Conveyor', 'Slicer Landing Conveyor', 'Slicer 1', 'Slicer 2', 'Slicer 3', 'Slicer 4'],
        'Washing': ['Speed Washer Conveyor', 'Air Sweep', 'Air Knife'],
        'Frying': ['Fryer', 'Main Oil Pump', 'Oil Management System', 'Fryer Catch Box'],
        'Optyx': ['FL710 Conveyor', 'Optyx', 'Recycle Conveyor', 'Rejection Conveyor', 'Rejection Vibratory', 'Crusher Unit', 'Optyx Outfeed Vibratory Conveyor'],
        'Seasoning': ['Divider Conveyor', 'Transfer Conveyor 1', 'Transfer Conveyor 2', 'Vibratory Conveyor Loop 1', 'Vibratory Conveyor Loop 2', 'Weighing Infeed Loop 1', 'Weighing Infeed Loop 2', 'Bulk Feeder Loop 1', 'Bulk Feeder Loop 2', 'Rospen Hopper Loop 1', 'Rospen Hopper Loop 2', 'Scarf Plate Loop 1', 'Scarf Plate Loop 2', 'Seasoning Tumbler Loop 1', 'Seasoning Tumbler Loop 2', 'Gooseneck Conveyor Loop 1', 'Gooseneck Conveyor Loop 2'],
    },
    'KKR': {
        'Blending': ['Blending System', 'Cablevey', 'Meal Hopper'],
        'Extrusion': ['Extruder 1', 'Extruder 2', 'Extruder 3', 'Extruder 4', 'Extruder 5'],
        'Transfer': ['Product Conveyor', 'Chaff Tumbler Infeed Z Conveyor'],
        'Chaff System': ['Chaff Tumbler', 'Vibratory Conveyor'],
        'Frying': ['Fryer', 'Fryer Exit Z Conveyor'],
        'Seasoning': ['Weighing Infeed Conveyor', 'Seasoning Tumbler', 'Seasoning Kettle', 'Retention Conveyor', 'Gooseneck Conveyor'],
    },
    'TWZ': {
        'Raw Material Handling': ['Bag Lifter', 'Meal Transfer Vertical Screw 1', 'Meal Transfer Vertical Screw 2', 'Ribbon Blender', 'Meal Transfer Blower', 'Meal Hopper'],
        'Dough Preparation': ['Doughkneader', 'Dough Transfer Conveyor'],
        'Extrusion': ['Extruder'],
        'Frying': ['Fryer', 'Main Oil Pump'],
        'Seasoning': ['Seasoning Infeed Inclined Conveyor', 'Vibratory Conveyor', 'Weighing Conveyor', 'Bulkfeeder', 'Seasoning Hopper', 'Seasoning Tumbler', 'Retention Conveyor', 'Gooseneck Conveyor'],
    },
    'BCP': {
        'Blending': ['Vertical Blender', 'Horizontal Blender', 'Meal Transfer System', 'Meal Hopper'],
        'Extrusion': ['Extruder'],
        'Product Transfer': ['Product Transfer Conveyor 1', 'Product Transfer Conveyor 2', 'Oven Infeed Inclined Conveyor'],
        'Baking': ['Oven Infeed Vibratory Conveyor', 'Oven', 'Oven Exit Z Conveyor'],
        'Seasoning': ['Vibratory Conveyor', 'Weighing Conveyor', 'Seasoning Kettle', 'Seasoning System', 'Seasoning Tumbler', 'Retention Conveyor', 'Gooseneck Conveyor'],
    },
}

PACKAGING_LINES = ['PC21 Packaging', 'PC32 Packaging', 'PC36 Packaging', 'KKR Packaging', 'TWZ Packaging', 'BCP Packaging', 'Palletizing']

CRITICAL_KEYWORDS = ['Fryer', 'Oven', 'Extruder', 'Main Oil Pump', 'Optyx', 'Oil Management']
HIGH_KEYWORDS = ['Peeler', 'Slicer', 'Washer', 'Tumbler', 'Blender', 'Heat Exchanger', 'Doughkneader', 'Blending', 'Crate Dumper', 'Seasoning Kettle', 'Seasoning System', 'Auto Halver']


def infer_criticality(name):
    for k in CRITICAL_KEYWORDS:
        if k.lower() in name.lower():
            return 'critical'
    for k in HIGH_KEYWORDS:
        if k.lower() in name.lower():
            return 'high'
    if 'pump' in name.lower() or 'motor' in name.lower() or 'screw' in name.lower():
        return 'high'
    return 'medium'


def infer_type(name):
    n = name.lower()
    for t, kws in [
        ('Conveyor', ['conveyor', 'gooseneck', 'cablevey']),
        ('Pump', ['pump']),
        ('Fryer', ['fryer']),
        ('Oven', ['oven']),
        ('Extruder', ['extruder']),
        ('Peeler', ['peeler']),
        ('Slicer', ['slicer', 'halver']),
        ('Washer', ['washer', 'hydrocyclone', 'dip washer']),
        ('Optical Sorter', ['optyx']),
        ('Heat Exchanger', ['heat exchanger']),
        ('Blender', ['blender', 'blending', 'kneader']),
        ('Hopper', ['hopper']),
        ('Feeder', ['feeder', 'bulkfeeder']),
        ('Tumbler', ['tumbler']),
        ('Vibratory Unit', ['vibratory']),
        ('Air System', ['air knife', 'air sweep', 'blower', 'dust collector']),
        ('Crusher', ['crusher']),
        ('Weigher', ['weighing']),
        ('Kettle', ['kettle']),
        ('Screw', ['screw']),
        ('Lifter', ['lifter', 'dumper']),
    ]:
        if any(k in n for k in kws):
            return t
    return 'General Equipment'


PG_ABBR_OVERRIDES = {'Trim & Pare': 'TRP', 'Chaff System': 'CHF', 'Raw Material Handling': 'RMH', 'Dough Preparation': 'DGH', 'Waste Handling': 'WST', 'Optical Sorting': 'OPT', 'Potato Receiving': 'REC', 'Product Transfer': 'PTR'}


def pg_abbr(pg):
    if pg in PG_ABBR_OVERRIDES:
        return PG_ABBR_OVERRIDES[pg]
    return ''.join(c for c in pg.upper() if c.isalpha())[:3]


FAILURE_MODES = [
    'Bearing Failure', 'Belt Failure', 'Chain Failure', 'Gearbox Failure', 'Motor Failure',
    'Seal Leakage', 'Coupling Failure', 'Shaft Misalignment', 'Excessive Vibration', 'Overheating',
    'Electrical Fault', 'Sensor Failure', 'VFD / Drive Fault', 'Pneumatic Failure', 'Hydraulic Failure',
    'Lubrication Failure', 'Blockage / Product Jam', 'Structural / Weld Failure', 'Instrumentation Fault', 'Utility Supply Failure',
]

ERROR_CODES = [
    {'code': 'OBS-01', 'label': 'Abnormal Vibration'},
    {'code': 'OBS-02', 'label': 'Abnormal Noise'},
    {'code': 'OBS-03', 'label': 'Oil / Lubricant Leakage'},
    {'code': 'OBS-04', 'label': 'Overheating / Hot Surface'},
    {'code': 'OBS-05', 'label': 'Loose Fastener / Guard'},
    {'code': 'OBS-06', 'label': 'Belt Wear / Tracking Issue'},
    {'code': 'OBS-07', 'label': 'Chain Slack / Wear'},
    {'code': 'OBS-08', 'label': 'Unusual Smell / Smoke'},
    {'code': 'OBS-09', 'label': 'Electrical Sparking / Tripping'},
    {'code': 'OBS-10', 'label': 'Product Quality Deviation'},
    {'code': 'OBS-11', 'label': 'Water / Steam Leakage'},
    {'code': 'OBS-12', 'label': 'Other Observation'},
]

PM_TEMPLATES = [
    {'name': 'Daily Operator Inspection', 'frequency': 'daily', 'priority': 'medium',
     'checklist': ['Machine Body — Leaks', 'Machine Body — Noise / Vibration', 'Safety — Guards', 'Area — Housekeeping'],
     'checklist_groups': [
         {'description': 'Machine Body', 'items': [
             {'checked_for': 'Leaks', 'parameter': 'Oil, water, air leakage'},
             {'checked_for': 'Noise / Vibration', 'parameter': 'Abnormal sound, vibration'},
         ]},
         {'description': 'Safety', 'items': [
             {'checked_for': 'Guards', 'parameter': 'All guards in place & secure'},
         ]},
         {'description': 'Area', 'items': [
             {'checked_for': 'Housekeeping', 'parameter': 'Clean, no obstructions'},
         ]},
     ]},
    {'name': 'Weekly Lubrication Round', 'frequency': 'weekly', 'priority': 'medium',
     'checklist': ['Bearings — Greasing', 'Gearbox — Oil level', 'Lubrication Lines — Condition'],
     'checklist_groups': [
         {'description': 'Bearings', 'items': [
             {'checked_for': 'Greasing', 'parameter': 'Grease per schedule'},
         ]},
         {'description': 'Gearbox', 'items': [
             {'checked_for': 'Oil level', 'parameter': 'Level in sight glass, top up if low'},
         ]},
         {'description': 'Lubrication Lines', 'items': [
             {'checked_for': 'Condition', 'parameter': 'No blockage / damage'},
         ]},
     ]},
    {'name': 'Monthly Mechanical Check', 'frequency': 'monthly', 'priority': 'high',
     'checklist': ['Motor — Bearing', 'Motor — Over load', 'Motor — Condition', 'Drive — Belt tension & wear', 'Drive — Chain tension & wear', 'Coupling — Alignment', 'Mounting — Bolts torque'],
     'checklist_groups': [
         {'description': 'Motor', 'items': [
             {'checked_for': 'Bearing', 'parameter': 'Vibration, Sound'},
             {'checked_for': 'Over load', 'parameter': 'Current draw vs rated'},
             {'checked_for': 'Condition', 'parameter': 'Temperature, mounting'},
         ]},
         {'description': 'Drive', 'items': [
             {'checked_for': 'Belt tension & wear', 'parameter': 'Deflection, cracks'},
             {'checked_for': 'Chain tension & wear', 'parameter': 'Slack, elongation'},
         ]},
         {'description': 'Coupling', 'items': [
             {'checked_for': 'Alignment', 'parameter': 'Runout, wear'},
         ]},
         {'description': 'Mounting', 'items': [
             {'checked_for': 'Bolts torque', 'parameter': 'Per torque spec'},
         ]},
     ]},
    {'name': 'Quarterly Electrical Inspection', 'frequency': 'quarterly', 'priority': 'high',
     'checklist': ['Panel — Thermal scan', 'Motor — Current draw', 'Cabling — Glands', 'Safety — Emergency stops', 'Panel — Filters'],
     'checklist_groups': [
         {'description': 'Panel', 'items': [
             {'checked_for': 'Thermal scan', 'parameter': 'Hot spots, terminals'},
             {'checked_for': 'Filters', 'parameter': 'Clean / replace'},
         ]},
         {'description': 'Motor', 'items': [
             {'checked_for': 'Current draw', 'parameter': 'Compare vs rated FLA'},
         ]},
         {'description': 'Cabling', 'items': [
             {'checked_for': 'Glands', 'parameter': 'Tightness, sealing'},
         ]},
         {'description': 'Safety', 'items': [
             {'checked_for': 'Emergency stops', 'parameter': 'Function test'},
         ]},
     ]},
    {'name': 'Yearly Major Overhaul Review', 'frequency': 'yearly', 'priority': 'critical',
     'checklist': ['Machine — Teardown inspection', 'Wear Parts — Replacement', 'Bearings — Assessment', 'Gearbox — Oil change', 'Instruments — Calibration'],
     'checklist_groups': [
         {'description': 'Machine', 'items': [
             {'checked_for': 'Teardown inspection', 'parameter': 'Full internal condition'},
         ]},
         {'description': 'Wear Parts', 'items': [
             {'checked_for': 'Replacement', 'parameter': 'Per wear limits'},
         ]},
         {'description': 'Bearings', 'items': [
             {'checked_for': 'Assessment', 'parameter': 'Clearance, noise, replace if due'},
         ]},
         {'description': 'Gearbox', 'items': [
             {'checked_for': 'Oil change', 'parameter': 'Drain, flush, refill'},
         ]},
         {'description': 'Instruments', 'items': [
             {'checked_for': 'Calibration', 'parameter': 'Sensors, gauges'},
         ]},
     ]},
]

RUNTIME_TEMPLATES = [
    {'name': '24/7 Continuous Operation', 'calendar_hours_per_day': 24, 'shifts': ['A (06:00-14:00)', 'B (14:00-22:00)', 'C (22:00-06:00)']},
    {'name': 'Two-Shift Operation', 'calendar_hours_per_day': 16, 'shifts': ['A (06:00-14:00)', 'B (14:00-22:00)']},
    {'name': 'Single-Shift Operation', 'calendar_hours_per_day': 8, 'shifts': ['A (08:00-16:00)']},
]

NOTIFICATION_TEMPLATES = [
    {'notif_type': 'report', 'title': 'New Machine Report', 'body': 'Report {code} submitted for {machine}', 'severity': 'info'},
    {'notif_type': 'breakdown', 'title': 'Breakdown Reported', 'body': '{ticket} \u2014 {machine}: {description}', 'severity': 'critical'},
    {'notif_type': 'critical_failure', 'title': 'CRITICAL Machine Failure', 'body': 'Critical machine {machine} is DOWN', 'severity': 'critical'},
    {'notif_type': 'work_order', 'title': 'Work Order Update', 'body': '{wo} \u2014 {machine}: {status}', 'severity': 'info'},
    {'notif_type': 'pm_due', 'title': 'PM Task Due', 'body': 'PM \u201c{task}\u201d due for {machine}', 'severity': 'warning'},
    {'notif_type': 'pm_overdue', 'title': 'PM Task OVERDUE', 'body': 'PM \u201c{task}\u201d overdue for {machine}', 'severity': 'critical'},
    {'notif_type': 'reliability_alert', 'title': 'Reliability Alert', 'body': '{machine} at {pct}% of predicted failure life', 'severity': 'warning'},
    {'notif_type': 'inspection_recommended', 'title': 'Inspection Recommended', 'body': '{machine} exceeded 80% of predicted failure life', 'severity': 'warning'},
]

SPARE_LOCATIONS = ['Rack A1', 'Rack A2', 'Rack A3', 'Rack B1', 'Rack B2', 'Rack B3', 'Process Store', 'Packaging Store', 'Utilities Store', 'Maintenance Workshop', 'Electrical Store', 'Mechanical Store']

SPARES = [
    ('400001234', 'Bearing 6205 ZZ', 'SKF Bearing 6205 Double Shielded', 'Rack A3', 24, 'EA', 'Bearings', 'SKF'),
    ('400001235', 'Bearing 6206 2RS', 'SKF Bearing 6206 Double Sealed', 'Rack A3', 18, 'EA', 'Bearings', 'SKF'),
    ('400001236', 'Bearing 6308 ZZ', 'FAG Bearing 6308 Double Shielded', 'Rack A3', 10, 'EA', 'Bearings', 'FAG'),
    ('400001237', 'Pillow Block UCP 207', 'NTN Pillow Block Bearing Unit UCP207', 'Rack A2', 8, 'EA', 'Bearings', 'NTN'),
    ('400002101', 'V Belt A57', 'Optibelt Classical V-Belt A57', 'Rack B1', 30, 'EA', 'Belts', 'Optibelt'),
    ('400002102', 'V Belt B62', 'Optibelt Classical V-Belt B62', 'Rack B1', 22, 'EA', 'Belts', 'Optibelt'),
    ('400002103', 'Timing Belt HTD 8M', 'Gates HTD 8M-1440 Timing Belt', 'Rack B1', 6, 'EA', 'Belts', 'Gates'),
    ('400002104', 'Modular Belt 500mm', 'Intralox S900 Modular Belt 500mm/m', 'Mechanical Store', 40, 'M', 'Belts', 'Intralox'),
    ('400003001', 'Mechanical Seal 25mm', 'Burgmann MG1 Mechanical Seal 25mm', 'Rack A1', 12, 'EA', 'Seals', 'EagleBurgmann'),
    ('400003002', 'Oil Seal 35x52x7', 'NBR Rotary Shaft Oil Seal 35x52x7', 'Rack A1', 40, 'EA', 'Seals', 'Freudenberg'),
    ('400003003', 'O-Ring Kit NBR', 'NBR O-Ring Assortment Kit 380pc', 'Rack A1', 5, 'KIT', 'Seals', 'Parker'),
    ('400004001', 'Oil Filter Element', 'Hydac Return Line Filter Element 10\u00b5m', 'Rack B2', 15, 'EA', 'Filters', 'Hydac'),
    ('400004002', 'Air Filter Cartridge', 'Donaldson Air Filter Cartridge P77', 'Rack B2', 9, 'EA', 'Filters', 'Donaldson'),
    ('400004003', 'Dust Collector Bag Set', 'Polyester Filter Bag Set for Dust Collector', 'Packaging Store', 4, 'SET', 'Filters', 'BWF'),
    ('400005001', 'Roller Chain 12B-1', 'Renold Roller Chain 12B-1 (5m box)', 'Rack B3', 7, 'BOX', 'Chains', 'Renold'),
    ('400005002', 'Chain Sprocket 12B 18T', 'Sprocket 12B-1 18 Teeth Hardened', 'Rack B3', 11, 'EA', 'Chains', 'Renold'),
    ('400006001', 'Gear Motor 1.5kW', 'SEW Eurodrive Gear Motor R37 1.5kW', 'Mechanical Store', 3, 'EA', 'Drives', 'SEW'),
    ('400006002', 'VFD 2.2kW', 'Danfoss FC302 Frequency Drive 2.2kW', 'Electrical Store', 4, 'EA', 'Drives', 'Danfoss'),
    ('400006003', 'Contactor 25A', 'Schneider LC1D25 Contactor 25A 24VDC', 'Electrical Store', 16, 'EA', 'Electrical', 'Schneider'),
    ('400006004', 'Proximity Sensor M18', 'IFM M18 Inductive Proximity Sensor PNP', 'Electrical Store', 20, 'EA', 'Electrical', 'IFM'),
    ('400006005', 'Photo Eye Sensor', 'SICK W12 Photoelectric Sensor', 'Electrical Store', 14, 'EA', 'Electrical', 'SICK'),
    ('400007001', 'Food Grade Grease', 'Kluber Klubersynth UH1 14-151 (1kg)', 'Maintenance Workshop', 25, 'EA', 'Lubricants', 'Kluber'),
    ('400007002', 'Gear Oil VG220', 'Mobil SHC 630 Gear Oil (20L pail)', 'Maintenance Workshop', 8, 'PAIL', 'Lubricants', 'Mobil'),
    ('400007003', 'Hydraulic Oil VG46', 'Shell Tellus S2 M46 (20L pail)', 'Utilities Store', 6, 'PAIL', 'Lubricants', 'Shell'),
    ('400008001', 'Pneumatic Cylinder 50x200', 'Festo DSBC-50-200 Pneumatic Cylinder', 'Rack B2', 5, 'EA', 'Pneumatics', 'Festo'),
    ('400008002', 'Solenoid Valve 5/2', 'Festo 5/2-Way Solenoid Valve 24VDC', 'Rack B2', 10, 'EA', 'Pneumatics', 'Festo'),
    ('400009001', 'Fryer Burner Nozzle', 'CNG Burner Nozzle Assembly for Fryer', 'Process Store', 6, 'EA', 'Process Parts', 'Heat & Control'),
    ('400009002', 'Oil Pump Impeller', 'SS316 Impeller for Main Oil Pump', 'Process Store', 3, 'EA', 'Process Parts', 'Heat & Control'),
    ('400009003', 'Slicer Blade Set', 'Urschel Slicer Blade Set (8pc)', 'Process Store', 12, 'SET', 'Process Parts', 'Urschel'),
    ('400009004', 'Peeler Abrasive Roller', 'Abrasive Peeling Roller Element', 'Process Store', 9, 'EA', 'Process Parts', 'Kiremko'),
]

RELIABILITY_SETTINGS = {
    'id': 'reliability_settings',
    'healthy_threshold_pct': 70,
    'watch_threshold_pct': 80,
    'inspection_threshold_pct': 100,
    'alert_trigger_pct': 80,
    'predictive_trigger_pct': 80,
    'level2_min_failures': 2,
    'level3_min_failures': 5,
    'rolling_window': 3,
    'root_cause_downtime_minutes': 30,
    'updated_at': None,
}


async def _dupe_check(coll, key):
    dupes = await db[coll].aggregate([
        {'$group': {'_id': f'${key}', 'n': {'$sum': 1}}}, {'$match': {'n': {'$gt': 1}}}, {'$limit': 20},
    ]).to_list(20)
    return [d['_id'] for d in dupes]


async def seed_all():
    """Idempotent master-data seeding. Each collection is verified independently;
    missing records are created, existing ones are never duplicated.
    Prints a per-collection summary at startup so gaps are immediately visible."""
    ts = now_iso()
    summary = {}

    # ---------- Users ----------
    existing_users = {u['username'] async for u in db.users.find({}, {'username': 1})}
    user_docs = [
        {'id': nid(), 'username': 'admin', 'password': hash_password('admin123'), 'role': 'admin', 'name': 'System Administrator', 'email': 'admin@factory.local', 'active': True, 'created_at': ts},
        # Technician roster from Pune plant records (default password: tech123 — change via Administration → Users)
        *[{'id': nid(), 'username': u, 'password': hash_password('tech123'), 'role': 'technician', 'name': n,
           'email': f'{u}@factory.local', 'active': True, 'created_at': ts} for u, n in [
            ('dattatray', 'Dattatray Rakshe'), ('nitin', 'Nitin Chavan'), ('ravindra', 'Ravindra Sonawane'),
            ('namdev', 'Namdev Shewale'), ('raju', 'Raju Daundkar'), ('premraj', 'Premraj Patil'),
            ('bhausaheb', 'Bhausaheb Kulal'), ('chandrakant', 'Chandrakant Bhole'), ('jalindar', 'Jalindar Kokate')]],
        {'id': nid(), 'username': 'operator', 'password': hash_password('operator123'), 'role': 'operator', 'name': 'Floor Operator', 'email': 'operator@factory.local', 'active': True, 'created_at': ts},
    ]
    new_users = [u for u in user_docs if u['username'] not in existing_users]
    if new_users:
        await db.users.insert_many([dict(u) for u in new_users])
    summary['users'] = {'created': len(new_users), 'total': await db.users.count_documents({})}

    # ---------- Lines (TOP-LEVEL — hierarchy is Line → Department → Process Group → Machine) ----------
    line_names = list(APPENDIX_A) + ['Palletizing', 'Utilities']
    line_map = {l['name']: l for l in await db.lines.find({}, {'_id': 0}).to_list(1000)}
    created = 0
    for order, name in enumerate(line_names):
        if name not in line_map:
            doc = {'id': nid(), 'name': name, 'order': order, 'created_at': ts}
            await db.lines.insert_one(dict(doc))
            line_map[name] = doc
            created += 1
    summary['lines'] = {'created': created, 'total': await db.lines.count_documents({})}

    # ---------- Departments (PER-LINE sub-records) ----------
    dept_defs = []  # (line, dept_name, order)
    for line_name in APPENDIX_A:
        dept_defs.append((line_name, 'PROCESS', 0))
        dept_defs.append((line_name, 'PACKAGING', 1))
    dept_defs.append(('Palletizing', 'PACKAGING', 1))
    dept_defs.append(('Utilities', 'UTILITIES', 2))
    dept_map = {(d['line'], d['name']): d for d in await db.departments.find({}, {'_id': 0}).to_list(1000)}
    created = 0
    for line_name, dname, order in dept_defs:
        if (line_name, dname) not in dept_map and line_name in line_map:
            doc = {'id': nid(), 'name': dname, 'line': line_name, 'line_id': line_map[line_name]['id'],
                   'order': order, 'created_at': ts}
            await db.departments.insert_one(dict(doc))
            dept_map[(line_name, dname)] = doc
            created += 1
    summary['departments'] = {'created': created, 'total': await db.departments.count_documents({})}

    # ---------- Process Groups (under each line's PROCESS department) ----------
    pg_map = {(p['line'], p['name']): p for p in await db.process_groups.find({}, {'_id': 0}).to_list(10000)}
    created = 0
    for line_name, pgs in APPENDIX_A.items():
        proc_dept = dept_map[(line_name, 'PROCESS')]
        for pg_order, pg_name in enumerate(pgs):
            if (line_name, pg_name) not in pg_map:
                doc = {'id': nid(), 'name': pg_name, 'line': line_name, 'line_id': line_map[line_name]['id'],
                       'department': 'PROCESS', 'department_id': proc_dept['id'], 'order': pg_order, 'created_at': ts}
                await db.process_groups.insert_one(dict(doc))
                pg_map[(line_name, pg_name)] = doc
                created += 1
    summary['process_groups'] = {'created': created, 'total': await db.process_groups.count_documents({})}

    # ---------- Machines (exact Appendix A; keyed by machine code) ----------
    existing_codes = {m['code'] async for m in db.machines.find({}, {'code': 1})}
    expected_codes = set()
    new_machines = []
    sap_seq = 10000001
    for line_name, pgs in APPENDIX_A.items():
        for pg_order, (pg_name, machine_names) in enumerate(pgs.items()):
            abbr = pg_abbr(pg_name)
            pg = pg_map[(line_name, pg_name)]
            for idx, mname in enumerate(machine_names):
                code = f"{line_name}-{abbr}-{idx + 1:03d}"
                expected_codes.add(code)
                if code not in existing_codes:
                    new_machines.append({
                        'id': nid(), 'name': mname, 'code': code, 'sap_code': str(sap_seq),
                        'department': 'PROCESS', 'department_id': dept_map[(line_name, 'PROCESS')]['id'],
                        'line': line_name, 'line_id': line_map[line_name]['id'],
                        'process_group': pg_name, 'process_group_id': pg['id'],
                        'machine_type': infer_type(mname), 'criticality': infer_criticality(mname),
                        'status': 'running', 'health': 'healthy', 'reliability_state': 'no_data',
                        'position_x': idx * 220, 'position_y': pg_order * 130, 'width': 200, 'height': 110,
                        'total_run_hours': 0.0, 'inspection_recommended': False,
                        'created_at': ts, 'commissioned_at': ts,
                    })
                sap_seq += 1
    if new_machines:
        await db.machines.insert_many([dict(m) for m in new_machines])
    dupes = await _dupe_check('machines', 'code')
    machine_total = await db.machines.count_documents({})
    missing = expected_codes - existing_codes - {m['code'] for m in new_machines}
    summary['machines'] = {'created': len(new_machines), 'total': machine_total,
                           'expected_from_appendix_a': len(expected_codes),
                           'missing': sorted(missing), 'duplicates': dupes}

    # ---------- Catalog collections (keyed) ----------
    async def ensure(coll, docs, key):
        existing = {d[key] async for d in db[coll].find({}, {key: 1})}
        new = [dict(d) for d in docs if d[key] not in existing]
        if new:
            await db[coll].insert_many(new)
        summary[coll] = {'created': len(new), 'total': await db[coll].count_documents({})}

    await ensure('failure_modes', [{'id': nid(), 'name': fm, 'active': True, 'created_at': ts} for fm in FAILURE_MODES], 'name')
    await ensure('error_codes', [{'id': nid(), **ec, 'active': True, 'created_at': ts} for ec in ERROR_CODES], 'code')
    await ensure('pm_templates', [{'id': nid(), **t, 'created_at': ts} for t in PM_TEMPLATES], 'name')
    # migrate existing templates: attach structured checklist_groups where missing
    for t in PM_TEMPLATES:
        if t.get('checklist_groups'):
            await db.pm_templates.update_one(
                {'name': t['name'], 'checklist_groups': {'$exists': False}},
                {'$set': {'checklist_groups': t['checklist_groups'], 'checklist': t['checklist']}})
    await ensure('runtime_templates', [{'id': nid(), **t, 'created_at': ts} for t in RUNTIME_TEMPLATES], 'name')
    await ensure('notification_templates', [{'id': nid(), **t, 'created_at': ts} for t in NOTIFICATION_TEMPLATES], 'notif_type')
    await ensure('spare_locations', [{'id': nid(), 'name': loc, 'active': True, 'created_at': ts} for loc in SPARE_LOCATIONS], 'name')
    await ensure('spares_inventory', [
        {'id': nid(), 'sap_code': s[0], 'material_name': s[1], 'long_text': s[2], 'location': s[3],
         'quantity': s[4], 'uom': s[5], 'category': s[6], 'manufacturer': s[7], 'vendor': s[7],
         'active': True, 'total_consumed': 0, 'created_at': ts, 'updated_at': ts}
        for s in SPARES
    ], 'sap_code')

    # ---------- Machine recommended spares (only when empty) ----------
    if await db.machine_spares.count_documents({}) == 0:
        machines_all = await db.machines.find({}, {'_id': 0}).to_list(20000)
        recs = []
        for m in [x for x in machines_all if x['name'] == 'Main Oil Pump']:
            for sap in ['400001234', '400003001', '400004001', '400002101', '400009002']:
                recs.append({'id': nid(), 'machine_id': m['id'], 'machine_name': m['name'], 'sap_code': sap, 'created_at': ts})
        slicers = [x for x in machines_all if x['machine_type'] == 'Slicer' and 'Slicer' in x['name'] and 'Conveyor' not in x['name']]
        for m in slicers[:8]:
            for sap in ['400009003', '400001235', '400002102']:
                recs.append({'id': nid(), 'machine_id': m['id'], 'machine_name': m['name'], 'sap_code': sap, 'created_at': ts})
        for m in [x for x in machines_all if x['name'] == 'Fryer']:
            for sap in ['400009001', '400003001', '400007002']:
                recs.append({'id': nid(), 'machine_id': m['id'], 'machine_name': m['name'], 'sap_code': sap, 'created_at': ts})
        if recs:
            await db.machine_spares.insert_many(recs)
        summary['machine_spares'] = {'created': len(recs), 'total': len(recs)}
    else:
        summary['machine_spares'] = {'created': 0, 'total': await db.machine_spares.count_documents({})}

    # ---------- Settings / branding / plant clock ----------
    created_settings = 0
    if not await db.settings.find_one({'id': 'reliability_settings'}):
        await db.settings.insert_one({**RELIABILITY_SETTINGS, 'updated_at': ts})
        created_settings += 1
    else:  # back-fill new keys added over time (never overwrite user-tuned values)
        await db.settings.update_one({'id': 'reliability_settings', 'predictive_trigger_pct': {'$exists': False}},
                                     {'$set': {'predictive_trigger_pct': 80}})
    if not await db.settings.find_one({'id': 'system_settings'}):
        await db.settings.insert_one({'id': 'system_settings', 'plant_name': 'Factory Operations Platform', 'timezone': 'UTC', 'updated_at': ts})
        created_settings += 1
    if not await db.settings.find_one({'id': 'plant_clock'}):
        await db.settings.insert_one({'id': 'plant_clock', 'started_at': ts, 'last_tick_at': ts})
        created_settings += 1
    if not await db.branding.find_one({'id': 'branding'}):
        await db.branding.insert_one({'id': 'branding', 'app_name': 'ForgeOps', 'plant_name': 'Snack Foods Factory', 'accent': '#00fff5', 'updated_at': ts})
        created_settings += 1
    summary['settings'] = {'created': created_settings, 'total': await db.settings.count_documents({})}

    # ---------- AM (Autonomous Maintenance) checklist template ----------
    # One representative per-machine template (Fryer example from the spec) so the
    # AM module ships non-empty. Idempotent: skipped once any template exists.
    if not await db.am_templates.find_one({}):
        fryer = await db.machines.find_one({'name': 'Fryer'}, {'_id': 0}) or await db.machines.find_one({}, {'_id': 0})
        if fryer:
            await db.am_templates.insert_one({
                'id': str(uuid.uuid4()), 'machine_id': fryer['id'], 'machine_name': fryer['name'],
                'line': fryer.get('line'), 'department': fryer.get('department'), 'process_group': fryer.get('process_group'),
                'template_name': f"AM — {fryer['name']}",
                'checklist_groups': [
                    {'description': 'Fryer', 'items': [
                        {'checked_for': 'Loose components', 'parameter': 'Visual — fasteners, fittings'},
                        {'checked_for': 'Oil level control', 'parameter': 'Level within min/max marks'},
                        {'checked_for': 'Conveyor belt tension', 'parameter': 'No sag / slippage'},
                        {'checked_for': 'Drive chain tension', 'parameter': 'Deflection within spec'},
                        {'checked_for': 'Hood limit switches', 'parameter': 'Trip / interlock functional'},
                        {'checked_for': 'Frame alignment', 'parameter': 'No visible distortion'},
                        {'checked_for': 'Moisture monitor', 'parameter': 'Reading plausible / no alarm'},
                        {'checked_for': 'Guards & covers', 'parameter': 'In place, secured'},
                    ]},
                    {'description': 'Oil Mist Eliminator', 'items': [
                        {'checked_for': 'Fan operation', 'parameter': 'No abnormal noise / vibration'},
                        {'checked_for': 'Mist carry-over', 'parameter': 'No visible mist at outlet'},
                        {'checked_for': 'Drain line', 'parameter': 'Free-flowing, no blockage'},
                    ]},
                    {'description': 'Motorized Catch Box', 'items': [
                        {'checked_for': 'Drive operation', 'parameter': 'Smooth travel, no jams'},
                        {'checked_for': 'Debris accumulation', 'parameter': 'Cleaned / acceptable'},
                        {'checked_for': 'Limit switches', 'parameter': 'End stops functional'},
                    ]},
                    {'description': 'Main Oil Pump', 'items': [
                        {'checked_for': 'Seal leakage', 'parameter': 'No drips at gland'},
                        {'checked_for': 'Abnormal noise / vibration', 'parameter': 'By ear / touch'},
                        {'checked_for': 'Discharge pressure', 'parameter': 'Within normal band'},
                    ]},
                ],
                'frequency': 'per_shift', 'active': True, 'created_at': ts, 'created_by': 'seed',
                'updated_at': None, 'updated_by': None,
            })
            summary['am_templates'] = {'created': 1}

    # ---------- Indexes ----------
    await db.machines.create_index('id')
    await db.machines.create_index([('line', 1), ('process_group', 1)])
    await db.breakdowns.create_index([('machine_id', 1), ('created_at', -1)])
    await db.breakdowns.create_index('status')
    await db.work_orders.create_index([('machine_id', 1), ('created_at', -1)])
    await db.work_orders.create_index('status')
    await db.pm_tasks.create_index('machine_id')
    await db.pm_tasks.create_index('next_due_date')
    await db.timeline_events.create_index([('created_at', -1)])
    await db.timeline_events.create_index([('machine_id', 1), ('created_at', -1)])
    await db.notifications.create_index([('created_at', -1)])
    await db.runtime_logs.create_index([('machine_id', 1), ('date', -1)])
    await db.spare_transactions.create_index([('sap_code', 1), ('created_at', -1)])
    await db.spares_inventory.create_index('sap_code', unique=True)
    await db.reliability_metrics.create_index('machine_id')
    await db.machine_reports.create_index([('machine_id', 1), ('created_at', -1)])
    await db.am_templates.create_index('machine_id')
    await db.am_submissions.create_index([('machine_id', 1), ('completed_at', -1)])
    await db.am_submissions.create_index([('template_id', 1), ('completed_at', -1)])
    await db.am_tasks.create_index([('schedule_id', 1), ('date', 1), ('shift', 1)], unique=True)
    await db.am_tasks.create_index([('machine_id', 1), ('date', -1)])
    await db.am_schedules.create_index('template_id')
    await db.audit_logs.create_index([('created_at', -1)])

    # ---------- Startup summary log ----------
    logger.info('=' * 60)
    logger.info('SEED VERIFICATION SUMMARY (idempotent)')
    for coll, info in summary.items():
        extra = ''
        if coll == 'machines':
            extra = f" | expected {info['expected_from_appendix_a']}"
            if info['missing']:
                extra += f" | MISSING: {info['missing']}"
            if info['duplicates']:
                extra += f" | DUPLICATES: {info['duplicates']}"
        logger.info(f"  {coll:<24} created={info.get('created', '?')} total={info.get('total', '?')}{extra}")
    logger.info('=' * 60)

    await db.settings.update_one({'id': 'seed_summary'}, {'$set': {'id': 'seed_summary', 'summary': summary, 'seeded_at': ts}}, upsert=True)
    await db.settings.update_one({'id': 'seed_complete'}, {'$set': {'id': 'seed_complete', 'seeded_at': ts, 'machine_count': machine_total}}, upsert=True)
    await seed_historical_breakdowns()
    return summary


async def seed_historical_breakdowns():
    """Seed the imported Pune historical breakdowns (seed_data/historical_breakdowns.json)
    on FIRST install only. Machine ids are resolved by (line, machine_name); each affected
    machine's commissioned_at is backdated to before its earliest breakdown (MTBF guard)."""
    import json
    path = os.path.join(os.path.dirname(__file__), 'seed_data', 'historical_breakdowns.json')
    if not os.path.exists(path):
        return
    if await db.breakdowns.count_documents({'reporter': 'excel-import'}) > 0:
        return  # already seeded/imported
    docs = json.load(open(path))
    machines = {(m['line'], m['name']): m for m in
                await db.machines.find({}, {'_id': 0, 'id': 1, 'name': 1, 'line': 1, 'commissioned_at': 1}).to_list(1000)}
    inserted, earliest = [], {}
    for d in docs:
        m = machines.get((d['line'], d['machine_name']))
        if not m:
            continue
        c = await db.counters.find_one_and_update({'_id': 'breakdowns'}, {'$inc': {'seq': 1}}, upsert=True, return_document=True)
        d = dict(d, id=nid(), machine_id=m['id'], ticket_number=f"BD-{c['seq']:05d}",
                 work_order_id=None, rca_task_id=None)
        earliest[m['id']] = min(earliest.get(m['id'], d['start_time']), d['start_time'])
        inserted.append(d)
    if inserted:
        await db.breakdowns.insert_many([dict(d) for d in inserted])
        from datetime import timedelta
        for mid, e in earliest.items():
            m = next(v for v in machines.values() if v['id'] == mid)
            comm = m.get('commissioned_at')
            if comm and str(comm) > e:
                await db.machines.update_one({'id': mid}, {'$set': {'commissioned_at':
                    (datetime.fromisoformat(e) - timedelta(days=1)).isoformat()}})
        logger.info(f'historical breakdowns seeded: {len(inserted)}/{len(docs)}')
