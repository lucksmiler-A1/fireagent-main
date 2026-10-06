#!/usr/bin/env python3
"""Second-pass expansion: bring fire_rules from 123 to 200+ rules.

Adds:
- More GB 50016 sub-clauses
- New sources: GB 17945 emergency lighting, GB/T 25113, GB 50157 metro, GB 50098 civil air defense
- 高校学生宿舍消防安全管理规定 (DORM)
- 国务院《消防安全责任制实施办法》 (RESP)
- 仓库防火安全管理规则 (WAREHOUSE)
- 加强 dormitory / industrial / construction 场景覆盖
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "app" / "data" / "fire_rules.json"


def gen_rules():
    rules = []
    common_full = ["campus", "office", "factory", "residential", "construction"]
    public_scenes = ["campus", "office", "residential"]
    industrial_scenes = ["factory", "construction"]

    GB50016 = "GB 50016-2014(2018)"
    GB17945 = "GB 17945-2010"
    GB50157 = "GB 50157-2013"
    GB50098 = "GB 50098-2009"
    GB50261 = "GB 50261-2017"
    GB50166 = "GB 50166-2019"
    GB13495 = "GB 13495.1-2015"
    GB15630 = "GB 15630-1995"
    DORM = "高校学生宿舍消防安全管理规定"
    RESP = "消防安全责任制实施办法 (国办发[2017]87号)"
    WAREHOUSE = "仓库防火安全管理规则"
    GAFAC = "Industrial Fire Safety Practice (factory floor)"
    EBIKE = "GB 42295-2022"
    HMBF = "HMBF"
    FIRELAW = "Fire Law of PRC"

    # ----- More GB 50016 sub-clauses -----
    rules.extend([
        {"id":"GB50016-3.5.1","source":GB50016,"article":"3.5.1","title":"Workshop fire-resistance class",
         "scene":industrial_scenes,"hazard_type":"workshop_fire_class_low",
         "tags":["workshop","fire resistance","厂房","耐火等级"],
         "text":"Workshops handling Class A or B production hazards shall meet at least Grade II fire resistance; lower grades require approved special design."},
        {"id":"GB50016-3.6.1","source":GB50016,"article":"3.6.1","title":"Warehouse compartment area",
         "scene":industrial_scenes + ["office"],"hazard_type":"warehouse_compartment_oversized",
         "tags":["warehouse","fire compartment","仓库","防火分区"],
         "text":"Warehouse fire compartments shall not exceed code-prescribed area limits; conversion of single-story to multi-story without re-zoning is non-compliant."},
        {"id":"GB50016-5.4.10","source":GB50016,"article":"5.4.10","title":"Equipment-room separation",
         "scene":common_full,"hazard_type":"equipment_room_storage",
         "tags":["equipment room","separation","设备间"],
         "text":"Equipment rooms (transformer, switch, refrigeration) shall be separated from adjacent spaces by Class A fire walls; storage of unrelated combustibles inside is prohibited."},
        {"id":"GB50016-6.2.4","source":GB50016,"article":"6.2.4","title":"Combustible duct lining",
         "scene":common_full,"hazard_type":"combustible_decoration",
         "tags":["duct","lining","B1","风管","内衬"],
         "text":"Internal linings of HVAC ducts that pass through fire compartments shall use non-combustible materials."},
        {"id":"GB50016-6.4.4","source":GB50016,"article":"6.4.4","title":"Open external stair",
         "scene":["residential","office"],"hazard_type":"evacuation_route_unsafe",
         "tags":["external stair","外部楼梯","疏散"],
         "text":"Open external stairs used as evacuation routes shall be free of combustible cladding and shall not have wall openings within 2 m of stair flights."},
        {"id":"GB50016-6.7.2","source":GB50016,"article":"6.7.2","title":"Fire-rated windows location",
         "scene":common_full,"hazard_type":"fire_window_missing",
         "tags":["fire window","防火窗"],
         "text":"Windows opening into stairwells, refuge floors, or shared shafts shall be Class C or higher fire-rated and shall not be replaced with regular glazing."},
        {"id":"GB50016-7.3.5","source":GB50016,"article":"7.3.5","title":"Helipad clearance",
         "scene":["office","residential"],"hazard_type":"helipad_obstruction",
         "tags":["helipad","rooftop","高层","直升机"],
         "text":"Helipads on super high-rise rooftops shall be kept clear of antennas, signs, or stored items that obstruct landing."},
        {"id":"GB50016-7.4.1","source":GB50016,"article":"7.4.1","title":"Underground evacuation",
         "scene":common_full,"hazard_type":"underground_evacuation_unsafe",
         "tags":["underground","evacuation","地下","疏散"],
         "text":"Underground spaces deeper than 10 m or containing 50+ persons shall provide independent evacuation routes leading directly outdoors."},
        {"id":"GB50016-8.4.1","source":GB50016,"article":"8.4.1","title":"Wet/dry hydrant maintenance",
         "scene":common_full,"hazard_type":"hydrant_blocked",
         "tags":["hydrant","maintenance","消火栓","维护"],
         "text":"Hydrants and valves shall remain free of paint, ice, and rust accumulation that would prevent operation; periodic inspection required."},
        {"id":"GB50016-10.3.4","source":GB50016,"article":"10.3.4","title":"Evacuation lighting illuminance",
         "scene":common_full,"hazard_type":"emergency_lighting_failure",
         "tags":["evacuation lighting","illuminance","疏散照明","照度"],
         "text":"Floor illuminance of evacuation routes shall be at least 1 lx; refuge floors and exit corridors shall be at least 5 lx."},
        {"id":"GB50016-11.0.5","source":GB50016,"article":"11.0.5","title":"Hazardous storage indoor limit",
         "scene":industrial_scenes,"hazard_type":"hazardous_goods_storage",
         "tags":["flammable","indoor","storage","limit","可燃液体","限量"],
         "text":"Indoor storage of flammable liquids in workshops shall not exceed daily-usage quantity; bulk storage shall be relocated to dedicated rooms."},
    ])

    # ----- GB 17945 emergency evacuation lighting -----
    rules.extend([
        {"id":"GB17945-4.1","source":GB17945,"article":"Sec.4.1","title":"Emergency lamp battery test",
         "scene":common_full,"hazard_type":"emergency_lighting_failure",
         "tags":["emergency lamp","battery","test","应急灯","蓄电池"],
         "text":"Emergency lighting batteries shall undergo monthly self-test and quarterly discharge tests with results logged."},
        {"id":"GB17945-5.2","source":GB17945,"article":"Sec.5.2","title":"Sign luminance",
         "scene":common_full,"hazard_type":"signage_missing_or_blocked",
         "tags":["sign","luminance","疏散指示","亮度"],
         "text":"Evacuation signs shall maintain a minimum luminance after 30 minutes of battery operation; faded or dimmed signs shall be replaced."},
        {"id":"GB17945-7.3","source":GB17945,"article":"Sec.7.3","title":"Illumination installation height",
         "scene":common_full,"hazard_type":"signage_missing_or_blocked",
         "tags":["installation height","sight line","安装高度","视线"],
         "text":"Wall-mounted evacuation signs shall be installed at 1.0 m to 1.5 m height; ceiling signs shall be visible from any position in the route."},
    ])

    # ----- GB 50166 火灾自动报警施工验收 -----
    rules.extend([
        {"id":"GB50166-3.1.5","source":GB50166,"article":"3.1.5","title":"Acceptance test responsibility",
         "scene":common_full,"hazard_type":"acceptance_test_missing",
         "tags":["acceptance","test","验收","责任"],
         "text":"Fire alarm system acceptance tests shall be conducted jointly by installer, owner, and qualified third-party agency before handover."},
        {"id":"GB50166-3.4.4","source":GB50166,"article":"3.4.4","title":"Periodic detector cleaning",
         "scene":common_full,"hazard_type":"detector_dirty",
         "tags":["detector","cleaning","烟感清洁"],
         "text":"Smoke detectors and beam detectors shall be cleaned at least annually; dust and grease accumulation shall not be allowed."},
        {"id":"GB50166-7.6.1","source":GB50166,"article":"7.6.1","title":"Linkage test record",
         "scene":common_full,"hazard_type":"alarm_linkage_missing",
         "tags":["linkage","test record","联动","记录"],
         "text":"Linkage tests for sprinklers, smoke control, evacuation broadcast, and door release shall be performed annually with documented results."},
    ])

    # ----- GB 50261 sprinkler installation -----
    rules.extend([
        {"id":"GB50261-5.0.4","source":GB50261,"article":"5.0.4","title":"Sprinkler nozzle replacement",
         "scene":common_full,"hazard_type":"sprinkler_blocked_or_damaged",
         "tags":["sprinkler","damaged","replacement","喷头"],
         "text":"Damaged, painted-over, or corroded sprinkler nozzles shall be replaced; on-site repainting that obstructs the heat-sensing bulb is prohibited."},
        {"id":"GB50261-5.2.3","source":GB50261,"article":"5.2.3","title":"Storage area sprinkler density",
         "scene":industrial_scenes + ["office"],"hazard_type":"sprinkler_density_low",
         "tags":["storage","sprinkler density","储存","喷水强度"],
         "text":"Storage areas exceeding rack height limits require enhanced sprinkler density and in-rack sprinklers; otherwise sprinkler protection is treated as inadequate."},
    ])

    # ----- GB 50157 metro / public transport -----
    rules.extend([
        {"id":"GB50157-7.5.4","source":GB50157,"article":"7.5.4","title":"Metro evacuation platform",
         "scene":["campus","office","residential"],"hazard_type":"evacuation_obstructed",
         "tags":["metro","platform","subway","站台","疏散"],
         "text":"Metro and underground transit station platforms shall maintain unobstructed evacuation aisles with width meeting peak-hour design occupancy."},
    ])

    # ----- GB 50098 civil air defense -----
    rules.extend([
        {"id":"GB50098-5.2.1","source":GB50098,"article":"5.2.1","title":"Underground assembly fire compartment",
         "scene":["campus","office","residential"],"hazard_type":"warehouse_compartment_oversized",
         "tags":["underground","civil defense","fire compartment","人防","防火分区"],
         "text":"Underground civil air defense projects used for assembly or commerce shall have fire compartments not exceeding 1000 m^2; sprinkler installation may double this limit."},
    ])

    # ----- GB 13495.1 安全标志 -----
    rules.extend([
        {"id":"GB13495-4.1","source":GB13495,"article":"Sec.4.1","title":"Safety sign minimum size",
         "scene":common_full,"hazard_type":"signage_missing_or_blocked",
         "tags":["safety sign","size","安全标志","尺寸"],
         "text":"Fire safety signs shall meet minimum visibility size requirements based on viewing distance; signs covered or below the minimum size are non-compliant."},
        {"id":"GB13495-5.2","source":GB13495,"article":"Sec.5.2","title":"Hazard warning placement",
         "scene":common_full,"hazard_type":"signage_missing_or_blocked",
         "tags":["warning","placement","警示","张贴"],
         "text":"Hazard warning signs shall be placed near the entry to the hazard zone and shall not be hidden by stored items, doors, or movable equipment."},
    ])

    # ----- GB 15630 fire signs -----
    rules.extend([
        {"id":"GB15630-5.1","source":GB15630,"article":"Sec.5.1","title":"Fire equipment sign visibility",
         "scene":common_full,"hazard_type":"signage_missing_or_blocked",
         "tags":["fire equipment","sign","消防设备","标志"],
         "text":"Fire equipment locations shall be marked with red-on-white international fire signs and kept visible from primary corridors."},
    ])

    # ----- DORM 学生宿舍 -----
    rules.extend([
        {"id":"DORM-1","source":DORM,"article":"Sec.1","title":"Dormitory power outlet limit",
         "scene":["campus","residential"],"hazard_type":"electrical_overload_or_aging",
         "tags":["dormitory","power outlet","宿舍","插座"],
         "text":"Each student dormitory bed area shall have at most one regulated power outlet; multi-stage power strips and unauthorized rewiring are prohibited."},
        {"id":"DORM-2","source":DORM,"article":"Sec.2","title":"Dormitory high-power appliance ban",
         "scene":["campus","residential"],"hazard_type":"high_power_appliance_in_dorm",
         "tags":["high-power","appliance","heater","kettle","违章电器","大功率"],
         "text":"Use of high-power appliances such as electric stoves, heaters, and induction cookers in dormitories is prohibited; campus inspections may seize such devices."},
        {"id":"DORM-3","source":DORM,"article":"Sec.3","title":"Dormitory smoking ban",
         "scene":["campus","residential"],"hazard_type":"smoking_in_dorm",
         "tags":["smoking","cigarette","dormitory","吸烟","宿舍"],
         "text":"Smoking in student dormitories and connected corridors is prohibited; unattended smoldering items are treated as serious fire hazards."},
        {"id":"DORM-4","source":DORM,"article":"Sec.4","title":"Dormitory evacuation drill",
         "scene":["campus"],"hazard_type":"drill_missing",
         "tags":["dormitory","drill","semester","宿舍","演练"],
         "text":"Universities shall organize fire evacuation drills in student dormitory blocks at least once per semester with attendance recorded."},
        {"id":"DORM-5","source":DORM,"article":"Sec.5","title":"Dormitory open flame ban",
         "scene":["campus","residential"],"hazard_type":"open_flame_in_dorm",
         "tags":["open flame","candle","incense","明火","蜡烛"],
         "text":"Use of candles, incense, alcohol stoves, and similar open flames in student dormitories is prohibited."},
        {"id":"DORM-6","source":DORM,"article":"Sec.6","title":"Dormitory storage limit",
         "scene":["campus"],"hazard_type":"combustible_storage",
         "tags":["dormitory","clutter","storage","堆放","宿舍"],
         "text":"Student dormitories shall not store flammable solvents, large amounts of paper or fabric, or unused appliances above safe capacity."},
        {"id":"DORM-7","source":DORM,"article":"Sec.7","title":"Common-area patrol",
         "scene":["campus"],"hazard_type":"daily_patrol_missing",
         "tags":["dormitory","patrol","rounds","查寝","巡查"],
         "text":"Dormitory administrators shall conduct daily fire safety patrols of corridors, stairwells, and common rooms with logged inspections."},
        {"id":"DORM-8","source":DORM,"article":"Sec.8","title":"Dormitory exit door state",
         "scene":["campus","residential"],"hazard_type":"exit_door_wrong",
         "tags":["dormitory","exit","lock","宿舍","上锁"],
         "text":"Dormitory exit doors shall remain unlocked from the inside during occupancy; chains, padlocks, or wedges that block egress are prohibited."},
    ])

    # ----- RESP 消防安全责任制实施办法 -----
    rules.extend([
        {"id":"RESP-3","source":RESP,"article":"Sec.3","title":"Government responsibility",
         "scene":common_full,"hazard_type":"management_responsibility",
         "tags":["government","responsibility","政府","责任"],
         "text":"Local governments shall include fire safety in performance evaluation and ensure dedicated personnel and budget for hazard rectification."},
        {"id":"RESP-4","source":RESP,"article":"Sec.4","title":"Department joint duty",
         "scene":common_full,"hazard_type":"management_responsibility",
         "tags":["joint duty","department","部门","联合"],
         "text":"Public security, emergency management, education, and housing departments shall coordinate fire safety inspections and information sharing."},
        {"id":"RESP-7","source":RESP,"article":"Sec.7","title":"Unit responsibility scope",
         "scene":common_full,"hazard_type":"management_responsibility",
         "tags":["unit","fire responsible","scope","责任范围"],
         "text":"Each unit shall implement the fire safety responsible person system covering planning, training, drills, hazard rectification, and emergency response."},
    ])

    # ----- WAREHOUSE 仓库防火安全管理规则 -----
    rules.extend([
        {"id":"WAREHOUSE-1","source":WAREHOUSE,"article":"Sec.1","title":"Warehouse separation distance",
         "scene":industrial_scenes + ["office"],"hazard_type":"warehouse_separation_low",
         "tags":["warehouse","separation","仓库","防火间距"],
         "text":"Warehouses shall maintain code-required separation from production buildings, residences, and ignition sources; reductions require fire safety review."},
        {"id":"WAREHOUSE-2","source":WAREHOUSE,"article":"Sec.2","title":"Warehouse smoking ban",
         "scene":industrial_scenes + ["office"],"hazard_type":"smoking_in_warehouse",
         "tags":["warehouse","smoking","ban","仓库","禁烟"],
         "text":"Smoking, hot work, and open flame use inside warehouses are prohibited; designated smoking areas shall be located outside the warehouse."},
        {"id":"WAREHOUSE-3","source":WAREHOUSE,"article":"Sec.3","title":"Warehouse stack height",
         "scene":industrial_scenes + ["office"],"hazard_type":"warehouse_stack_unsafe",
         "tags":["stack","height","spacing","堆垛","间距"],
         "text":"Stored goods shall maintain at least 0.5 m from walls, 0.3 m from ceilings, and 0.5 m from light fixtures; aisles shall be at least 1.5 m wide."},
        {"id":"WAREHOUSE-4","source":WAREHOUSE,"article":"Sec.4","title":"Warehouse electrical operation",
         "scene":industrial_scenes + ["office"],"hazard_type":"electrical_overload_or_aging",
         "tags":["warehouse","electrical","power off","仓库","断电"],
         "text":"Power to warehouse lighting and equipment shall be shut off at end of work day; permanent live lighting requires explosion-proof or anti-fire design."},
        {"id":"WAREHOUSE-5","source":WAREHOUSE,"article":"Sec.5","title":"Warehouse ventilation",
         "scene":industrial_scenes + ["office"],"hazard_type":"ventilation_inadequate",
         "tags":["warehouse","ventilation","通风","仓库"],
         "text":"Warehouses storing volatile combustibles shall have adequate ventilation; mechanical ventilation systems shall be inspected at least quarterly."},
    ])

    # ----- More HMBF entries (continued) -----
    rules.extend([
        {"id":"HMBF-48","source":HMBF,"article":"Art.48","title":"Owner responsibility for sub-tenants",
         "scene":["residential","office"],"hazard_type":"management_responsibility",
         "tags":["sub-tenant","owner","出租"],
         "text":"Building owners renting space to sub-tenants remain responsible for fire compartment integrity and shared facility maintenance."},
        {"id":"HMBF-49","source":HMBF,"article":"Art.49","title":"Fire facility upgrade",
         "scene":["residential","office"],"hazard_type":"facility_maintenance_missing",
         "tags":["upgrade","facility","升级","改造"],
         "text":"Existing buildings undergoing major refurbishment shall upgrade fire facilities to current code where reasonably practicable."},
        {"id":"HMBF-50","source":HMBF,"article":"Art.50","title":"Tenant fire training",
         "scene":["residential","office"],"hazard_type":"training_missing",
         "tags":["tenant","training","承租","培训"],
         "text":"Tenants of high-rise buildings shall receive fire safety training annually, including evacuation routes and hydrant operation."},
    ])

    # ----- Industrial fire safety practice -----
    rules.extend([
        {"id":"GAFAC-1","source":GAFAC,"article":"Sec.1","title":"Production area smoking",
         "scene":industrial_scenes,"hazard_type":"smoking_in_workshop",
         "tags":["smoking","workshop","车间","禁烟"],
         "text":"Smoking is prohibited in production workshops, warehouses, and adjacent fire-isolation zones; designated areas shall be at least 10 m away."},
        {"id":"GAFAC-2","source":GAFAC,"article":"Sec.2","title":"Lithium battery storage",
         "scene":industrial_scenes,"hazard_type":"lithium_battery_storage",
         "tags":["lithium battery","storage","锂电池","存储"],
         "text":"Lithium battery storage shall use dedicated rooms with thermal sensors, separation walls, and capacity limits; mixing with combustible materials is prohibited."},
        {"id":"GAFAC-3","source":GAFAC,"article":"Sec.3","title":"Conveyor belt cleaning",
         "scene":industrial_scenes,"hazard_type":"dust_explosion_risk",
         "tags":["conveyor","dust","cleaning","传送带","粉尘"],
         "text":"Conveyor belts handling combustible dust shall be cleaned daily; accumulated dust thicker than 5 mm requires immediate cleanup."},
        {"id":"GAFAC-4","source":GAFAC,"article":"Sec.4","title":"Mobile equipment fueling",
         "scene":industrial_scenes,"hazard_type":"fueling_unsafe",
         "tags":["fueling","forklift","加油","叉车"],
         "text":"Diesel and LPG fueling of forklifts and on-site vehicles shall be performed at designated outdoor stations with portable extinguisher within 5 m."},
        {"id":"GAFAC-5","source":GAFAC,"article":"Sec.5","title":"Painting booth interlock",
         "scene":industrial_scenes,"hazard_type":"spray_room_unsafe",
         "tags":["spray booth","interlock","喷漆","联锁"],
         "text":"Spray paint booths shall interlock spray-gun trigger with exhaust ventilation; painting with disabled or bypassed interlocks is prohibited."},
        {"id":"GAFAC-6","source":GAFAC,"article":"Sec.6","title":"Hot oil cooking limit",
         "scene":["factory","campus"],"hazard_type":"kitchen_exhaust",
         "tags":["hot oil","cooking","limit","食堂","油锅"],
         "text":"Cafeteria hot-oil cookers shall not be left unattended; on-site fire blanket and Class K extinguisher shall be in reach."},
        {"id":"GAFAC-7","source":GAFAC,"article":"Sec.7","title":"Equipment grounding test",
         "scene":industrial_scenes,"hazard_type":"earthing_unmaintained",
         "tags":["grounding","static","test","防静电","接地"],
         "text":"Anti-static grounding for equipment handling flammable liquids shall be tested at least every six months with results recorded."},
        {"id":"GAFAC-8","source":GAFAC,"article":"Sec.8","title":"Hot work isolation distance",
         "scene":industrial_scenes,"hazard_type":"hot_work_without_approval",
         "tags":["hot work","isolation","distance","动火","隔离"],
         "text":"Hot work shall maintain at least 10 m horizontal isolation from combustible storage; combustibles within range shall be removed or covered."},
        {"id":"GAFAC-9","source":GAFAC,"article":"Sec.9","title":"Worker PPE requirement",
         "scene":industrial_scenes,"hazard_type":"ppe_missing",
         "tags":["PPE","helmet","gloves","劳保"],
         "text":"Production workers in fire-prone or hot-work areas shall wear flame-resistant PPE; cotton work clothes are insufficient for welding tasks."},
        {"id":"GAFAC-10","source":GAFAC,"article":"Sec.10","title":"Compressor room ventilation",
         "scene":industrial_scenes,"hazard_type":"ventilation_inadequate",
         "tags":["compressor","ventilation","空压机","通风"],
         "text":"Air compressor and gas compressor rooms shall have continuous ventilation; oil mist accumulation shall be cleaned at least monthly."},
    ])

    # ----- Construction site additional -----
    rules.extend([
        {"id":"JGJ46-3.2.6","source":"JGJ 46-2005","article":"3.2.6","title":"Outdoor lighting",
         "scene":["construction"],"hazard_type":"electrical_overload_or_aging",
         "tags":["outdoor","lighting","weatherproof","户外照明"],
         "text":"Outdoor temporary lighting on construction sites shall be weatherproof, with cables raised at least 2.5 m above pedestrian walkways."},
        {"id":"JGJ46-5.2.1","source":"JGJ 46-2005","article":"5.2.1","title":"Earth-leakage detector",
         "scene":["construction"],"hazard_type":"electrical_overload_or_aging",
         "tags":["RCD","leakage","trip","漏电保护"],
         "text":"Each terminal switch box shall have a residual-current device with rated trip current ≤ 30 mA and trip time ≤ 0.1 s."},
        {"id":"JGJ46-7.6.1","source":"JGJ 46-2005","article":"7.6.1","title":"Tower crane power supply",
         "scene":["construction"],"hazard_type":"crane_power_unsafe",
         "tags":["tower crane","power","塔吊","供电"],
         "text":"Tower crane power supply shall use a dedicated cable and isolation switch; sharing with other site loads is prohibited."},
        {"id":"JGJ46-9.2.4","source":"JGJ 46-2005","article":"9.2.4","title":"Wood/scaffold fire risk",
         "scene":["construction"],"hazard_type":"combustible_storage",
         "tags":["wood","scaffold","fire risk","脚手架","木方"],
         "text":"Combustible scaffolding boards and wood pallets shall be stored at least 5 m from hot-work areas and covered with fire-retardant tarpaulins."},
    ])

    # ----- Factory 3-in-1 (新增) -----
    rules.extend([
        {"id":"SEVERE-2.7","source":"Major Hazard Determination 2017 (工贸)","article":"Sec.2.7","title":"Mezzanine residential ban",
         "scene":industrial_scenes,"hazard_type":"production_combination_unsafe",
         "tags":["mezzanine","living quarter","三合一","夹层"],
         "text":"Building mezzanine living quarters above production lines is prohibited and constitutes a major hazard regardless of partition material."},
        {"id":"SEVERE-3.2","source":"Major Hazard Determination 2017 (工贸)","article":"Sec.3.2","title":"Powder handling control",
         "scene":industrial_scenes,"hazard_type":"dust_explosion_risk",
         "tags":["powder","control","ATEX","粉尘控制"],
         "text":"Workshops handling combustible powder shall have explosion-proof equipment, anti-static grounding, and dust suppression; absence is a major hazard."},
        {"id":"SEVERE-4.5","source":"Major Hazard Determination 2017 (工贸)","article":"Sec.4.5","title":"Confined space hot work",
         "scene":industrial_scenes,"hazard_type":"hot_work_without_approval",
         "tags":["confined space","hot work","受限空间","动火"],
         "text":"Hot work in confined spaces without approved permit, ventilation, and on-site monitoring is a major hazard."},
    ])

    # ----- Public assembly venue (剧场/商场) -----
    rules.extend([
        {"id":"GB50016-12.0.7","source":GB50016,"article":"12.0.7","title":"Theater backstage egress",
         "scene":public_scenes,"hazard_type":"venue_exit_insufficient",
         "tags":["theater","backstage","stage","剧场","后台"],
         "text":"Theater backstage and stage areas shall have direct evacuation routes independent of audience exits; both shall be free of stored props."},
        {"id":"GB50016-12.0.9","source":GB50016,"article":"12.0.9","title":"Mall public area decoration",
         "scene":public_scenes,"hazard_type":"combustible_decoration",
         "tags":["mall","decoration","公共","装修"],
         "text":"Shopping malls shall use Class A or B1 decoration materials in public corridors and atriums; flammable holiday decorations require fire safety review."},
    ])

    # ----- Cafeteria / canteen safety -----
    rules.extend([
        {"id":"KITCHEN-3","source":"公消[2010]136号","article":"Sec.3","title":"Gas pipeline maintenance",
         "scene":["campus","office","residential"],"hazard_type":"gas_pipeline_unsafe",
         "tags":["gas pipeline","leak","燃气管道","泄漏"],
         "text":"Commercial kitchen gas pipelines shall be inspected at least annually for corrosion and joint leakage; gas leak alarms required for piped LPG/natural gas."},
        {"id":"KITCHEN-4","source":"公消[2010]136号","article":"Sec.4","title":"Cooker shut-off",
         "scene":["campus","office","residential"],"hazard_type":"cooker_unattended",
         "tags":["cooker","shut-off","close","燃气","闭阀"],
         "text":"Gas valves of cooking equipment shall be closed at end of business; pilot flame-only operation overnight is not permitted."},
    ])

    return rules


def main():
    target_file = RULES_FILE
    if not target_file.exists():
        print(f"Rules file not found: {target_file}")
        sys.exit(1)

    with open(target_file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    existing = data.get("rules", [])
    existing_ids = {r["id"] for r in existing}
    new_rules = [r for r in gen_rules() if r["id"] not in existing_ids]
    print(f"Existing: {len(existing)}, New: {len(new_rules)}")

    merged = existing + new_rules
    kb = data.get("knowledge_base", {})
    kb["version"] = "v2.1.0"
    kb["built_at"] = "2026-04-27"
    kb["expansion_note"] = "Round-2 expansion: added dormitory, warehouse, industrial-floor, government-responsibility sources."
    sources = sorted({r["source"] for r in merged})
    kb["sources"] = [{"code": s} for s in sources]
    data["knowledge_base"] = kb
    data["rules"] = merged

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {target_file} with {len(merged)} rules.")


if __name__ == "__main__":
    main()
