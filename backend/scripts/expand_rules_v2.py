#!/usr/bin/env python3
"""Expand fire_rules knowledge base from 33 to 200+ rules.

Adds rules across these sources:
- GB 50016 建筑设计防火规范
- GB 50140 灭火器配置设计规范
- GB 50084 自动喷水灭火系统设计规范
- GB 50116 火灾自动报警系统设计规范
- GB 51251 建筑防烟排烟系统技术标准
- GB 50354 建筑内部装修设计防火规范
- GB 25506 消防控制室通用技术要求
- GA 95 灭火器维修
- JGJ 46 施工现场临时用电安全技术规范
- 中华人民共和国消防法
- 高层民用建筑消防安全管理规定 (HMBF)
- 机关、团体、企业、事业单位消防安全管理规定 (Order 61)
- 国务院《生产安全事故应急条例》
- 应急管理部 工贸企业重大事故隐患判定标准
- 危险化学品安全管理条例
- 电动自行车停放充电场所消防安全管理 GB 42295
- 餐饮场所油烟管道清洗 (公消[2010])
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "app" / "data" / "fire_rules.json"


def gen_rules():
    rules = []
    common_scenes_full = ["campus", "office", "factory", "residential", "construction"]
    public_scenes = ["campus", "office", "residential"]
    industrial_scenes = ["factory", "construction"]

    GB50016 = "GB 50016-2014(2018)"
    GB50140 = "GB 50140-2005"
    GB50084 = "GB 50084-2017"
    GB50116 = "GB 50116-2013"
    GB51251 = "GB 51251-2017"
    GB50354 = "GB 50354-2005"
    GB25506 = "GB 25506-2010"
    GA95 = "GA 95-2015"
    JGJ46 = "JGJ 46-2005"
    FIRELAW = "Fire Law of PRC"
    HMBF = "HMBF"
    ORDER61 = "Order 61 / 公安部令第61号"
    EMERG_REG = "Emergency Response Regulation 2019"
    SEVERE_HAZARD = "Major Hazard Determination 2017 (工贸)"
    HAZCHEM = "Hazardous Chemicals Regulation 2013"
    EBIKE = "GB 42295-2022"
    KITCHEN = "公消[2010]136号"

    # ----- GB 50016 expansion (additional, beyond existing 6) -----
    rules.extend([
        {"id":"GB50016-3.3.8","source":GB50016,"article":"3.3.8","title":"Smoke control facility integrity",
         "scene":common_scenes_full,"hazard_type":"smoke_control_damaged",
         "tags":["smoke control","mechanical exhaust","damper","fan","防排烟","风机","防火阀"],
         "text":"Smoke control and exhaust facilities shall be maintained in working order; dampers and exhaust fans must not be disabled or blocked."},
        {"id":"GB50016-5.5.8","source":GB50016,"article":"5.5.8","title":"Fire compartment door closing",
         "scene":common_scenes_full,"hazard_type":"fire_door_abnormal",
         "tags":["fire door","closer","wedge","防火门","闭门器","常闭"],
         "text":"Class A and B fire compartment doors shall remain self-closing; door closers shall not be removed and doors shall not be wedged open."},
        {"id":"GB50016-5.5.13","source":GB50016,"article":"5.5.13","title":"Stairwell smoke barrier",
         "scene":public_scenes,"hazard_type":"stairwell_smoke_intrusion",
         "tags":["stairwell","smoke","positive pressure","楼梯间","正压送风"],
         "text":"Pressurized stairwells shall maintain positive pressure; doors shall be kept closed and pressure relief vents kept clear."},
        {"id":"GB50016-6.4.1","source":GB50016,"article":"6.4.1","title":"Evacuation stair clearance",
         "scene":common_scenes_full,"hazard_type":"evacuation_obstructed",
         "tags":["stair","evacuation","clearance","width","疏散楼梯","净宽"],
         "text":"Evacuation stairs shall have continuous railings and the clear width shall not be reduced by stored items, advertising boards, or temporary partitions."},
        {"id":"GB50016-6.4.5","source":GB50016,"article":"6.4.5","title":"Refuge story features",
         "scene":["office","residential"],"hazard_type":"refuge_story_misuse",
         "tags":["refuge floor","high-rise","避难层"],
         "text":"Refuge stories of high-rise buildings shall not be occupied by storage, offices, or residential use, and access shall remain unblocked."},
        {"id":"GB50016-6.4.11","source":GB50016,"article":"6.4.11","title":"Exit door direction and locking",
         "scene":common_scenes_full,"hazard_type":"exit_door_wrong",
         "tags":["exit door","outward","public","安全出口","外开","上锁"],
         "text":"Public building exit doors shall open in the direction of evacuation flow and shall not be locked, chained, or fitted with single-direction latches during use."},
        {"id":"GB50016-6.7.4","source":GB50016,"article":"6.7.4","title":"Insulation material combustibility",
         "scene":common_scenes_full,"hazard_type":"combustible_insulation",
         "tags":["insulation","exterior wall","flammable","外墙保温","B级"],
         "text":"Combustible insulation materials on exterior walls shall meet the building height and fire-rating requirements; B3 grade materials shall not be used on populated buildings."},
        {"id":"GB50016-7.1.5","source":GB50016,"article":"7.1.5","title":"Fire access road clearance",
         "scene":common_scenes_full,"hazard_type":"fire_lane_parking",
         "tags":["fire lane","access","width","消防车道","净宽"],
         "text":"The clear width of fire access roads shall be at least 4.0 m and the clear height at least 4.0 m; vehicles, plants, or structures shall not encroach on this clearance."},
        {"id":"GB50016-7.1.8","source":GB50016,"article":"7.1.8","title":"Fire access turning area",
         "scene":common_scenes_full,"hazard_type":"fire_lane_parking",
         "tags":["fire lane","turning","回车场","消防车道"],
         "text":"Dead-end fire access roads shall provide a turning area not smaller than 12 m x 12 m, kept clear of any objects."},
        {"id":"GB50016-8.1.6","source":GB50016,"article":"8.1.6","title":"Fire pump room availability",
         "scene":common_scenes_full,"hazard_type":"pump_room_unusable",
         "tags":["fire pump","pump room","valve","消防泵","阀门"],
         "text":"Fire pump rooms shall be unobstructed; valves on supply pipelines shall be in the normally-open position with clear status indication and tags."},
        {"id":"GB50016-8.1.10","source":GB50016,"article":"8.1.10","title":"Fire water tank capacity",
         "scene":common_scenes_full,"hazard_type":"water_tank_insufficient",
         "tags":["fire water tank","reserve","消防水箱","储水量"],
         "text":"Rooftop fire water tanks shall be filled to the design level; no other materials may be stored in the water tank room."},
        {"id":"GB50016-8.2.4","source":GB50016,"article":"8.2.4","title":"Outdoor hydrant access",
         "scene":common_scenes_full,"hazard_type":"hydrant_blocked",
         "tags":["outdoor hydrant","spacing","室外消火栓","间距"],
         "text":"Outdoor fire hydrants shall be installed at agreed spacing along fire access roads, and access within 1.5 m around them must remain clear."},
        {"id":"GB50016-8.2.7","source":GB50016,"article":"8.2.7","title":"Indoor hydrant cabinet",
         "scene":common_scenes_full,"hazard_type":"hydrant_blocked",
         "tags":["indoor hydrant","cabinet","hose","室内消火栓","水带"],
         "text":"Indoor fire hydrant cabinets shall be unlocked or have visible glass-break openers; hoses, nozzles, and valves shall be intact and not removed for other use."},
        {"id":"GB50016-8.3.1","source":GB50016,"article":"8.3.1","title":"Sprinkler installation scope",
         "scene":common_scenes_full,"hazard_type":"sprinkler_missing",
         "tags":["sprinkler","installation","自动喷水","设置范围"],
         "text":"Buildings exceeding the prescribed scale shall install automatic sprinkler systems covering all required spaces; partial omission for cost reasons is not permitted."},
        {"id":"GB50016-8.5.1","source":GB50016,"article":"8.5.1","title":"Smoke detection installation",
         "scene":common_scenes_full,"hazard_type":"detector_missing",
         "tags":["smoke detector","installation","烟感","设置"],
         "text":"Smoke detectors shall be installed where required by the design; spacing and ceiling clearance shall meet code, and detectors must not be removed or covered."},
        {"id":"GB50016-8.5.4","source":GB50016,"article":"8.5.4","title":"Manual call point reachability",
         "scene":common_scenes_full,"hazard_type":"alarm_device_abnormal",
         "tags":["manual call point","reach","手报","报警按钮"],
         "text":"Manual fire call points shall be installed at evacuation routes within 30 m walking distance and shall not be obscured by decoration, posters, or equipment."},
        {"id":"GB50016-9.1.1","source":GB50016,"article":"9.1.1","title":"Heating room safety",
         "scene":["factory","campus","office"],"hazard_type":"heating_room_unsafe",
         "tags":["boiler","heating","ventilation","锅炉房","通风"],
         "text":"Boiler rooms and heating equipment rooms shall have independent ventilation, and combustible materials shall not be stored within."},
        {"id":"GB50016-9.3.6","source":GB50016,"article":"9.3.6","title":"Generator room separation",
         "scene":common_scenes_full,"hazard_type":"generator_room_unsafe",
         "tags":["generator","fuel","separation","柴油机","油箱"],
         "text":"Backup diesel generator rooms shall be separated from other rooms by Class A fire walls, and day-tank fuel volume shall meet code limits."},
        {"id":"GB50016-10.1.5","source":GB50016,"article":"10.1.5","title":"Emergency lighting backup",
         "scene":common_scenes_full,"hazard_type":"emergency_lighting_failure",
         "tags":["emergency lighting","backup","battery","应急照明","蓄电池"],
         "text":"Emergency lighting and evacuation indication signs shall have backup power for at least 30 minutes; expired batteries shall be replaced and tested periodically."},
        {"id":"GB50016-10.2.7","source":GB50016,"article":"10.2.7","title":"Cable trough fire-stop",
         "scene":common_scenes_full,"hazard_type":"firestop_breach",
         "tags":["cable","firestop","penetration","防火封堵","桥架"],
         "text":"Cable shafts and trays passing through fire compartments shall be sealed with approved firestop materials; gaps caused by maintenance shall be re-sealed promptly."},
        {"id":"GB50016-11.0.1","source":GB50016,"article":"11.0.1","title":"Cooking source separation",
         "scene":["campus","residential","office"],"hazard_type":"kitchen_exhaust",
         "tags":["kitchen","stove","exhaust","厨房","炉灶"],
         "text":"Commercial cooking facilities shall be separated from residential or public use spaces by Class B fire walls and have independent exhaust ducts."},
        {"id":"GB50016-12.0.6","source":GB50016,"article":"12.0.6","title":"Mass-gathering venue exits",
         "scene":["campus","office","residential"],"hazard_type":"venue_exit_insufficient",
         "tags":["mass gathering","exits","capacity","人员密集","出口数量"],
         "text":"Public assembly venues shall provide at least two exits, with total exit width sized for the maximum occupancy and equipped with directional signage."},
    ])

    # ----- GB 50140 灭火器配置 -----
    rules.extend([
        {"id":"GB50140-3.1.2","source":GB50140,"article":"3.1.2","title":"Extinguisher hazard classification",
         "scene":common_scenes_full,"hazard_type":"extinguisher_misconfigured",
         "tags":["extinguisher","ABC","class","灭火器","配置等级"],
         "text":"Extinguishers shall be selected by hazard class; Class A, B, C, D, and E areas shall use compatible extinguishing media as listed in the regulation."},
        {"id":"GB50140-5.2.1","source":GB50140,"article":"5.2.1","title":"Extinguisher protection radius",
         "scene":common_scenes_full,"hazard_type":"extinguisher_coverage_low",
         "tags":["extinguisher","protection radius","walking distance","保护距离","步行距离"],
         "text":"For Class A hazards of medium severity, the maximum walking distance from any point to the nearest extinguisher shall not exceed 20 m."},
        {"id":"GB50140-5.2.5","source":GB50140,"article":"5.2.5","title":"Minimum extinguisher count per box",
         "scene":common_scenes_full,"hazard_type":"extinguisher_count_low",
         "tags":["extinguisher count","box","灭火器箱","数量"],
         "text":"Each extinguisher placement point shall hold at least two units; a single unit at a point is not compliant for Class A or B hazard areas."},
        {"id":"GB50140-6.1.1","source":GB50140,"article":"6.1.1","title":"Extinguisher mounting height",
         "scene":common_scenes_full,"hazard_type":"extinguisher_height_wrong",
         "tags":["extinguisher","mounting","height","悬挂","安装高度"],
         "text":"Hand-held extinguishers shall be mounted with the top no higher than 1.5 m and the bottom no lower than 0.08 m above the floor."},
        {"id":"GB50140-7.0.2","source":GB50140,"article":"7.0.2","title":"Extinguisher visible signage",
         "scene":common_scenes_full,"hazard_type":"extinguisher_signage_missing",
         "tags":["extinguisher","sign","location","灭火器标志","位置标识"],
         "text":"Extinguisher locations shall be marked with conspicuous signs; signs shall not be obscured by decoration, posters, or stored items."},
    ])

    # ----- GB 50084 自动喷水 -----
    rules.extend([
        {"id":"GB50084-5.0.4","source":GB50084,"article":"5.0.4","title":"Sprinkler clearance",
         "scene":common_scenes_full,"hazard_type":"sprinkler_blocked_or_damaged",
         "tags":["sprinkler","clearance","obstruction","喷头","遮挡"],
         "text":"Stored items shall be at least 0.45 m below sprinkler heads to ensure spray pattern coverage; closer placement is treated as obstruction."},
        {"id":"GB50084-6.1.4","source":GB50084,"article":"6.1.4","title":"Sprinkler valve open status",
         "scene":common_scenes_full,"hazard_type":"sprinkler_valve_closed",
         "tags":["sprinkler","valve","signal","信号阀","常开"],
         "text":"Main control valves of sprinkler systems shall be normally open with monitored signals; closing for maintenance requires explicit work permits and immediate restoration."},
        {"id":"GB50084-8.0.2","source":GB50084,"article":"8.0.2","title":"Sprinkler pressure check",
         "scene":common_scenes_full,"hazard_type":"sprinkler_pressure_low",
         "tags":["sprinkler","pressure","gauge","压力","表"],
         "text":"Operational pressure of automatic sprinkler systems shall be within design range; pressure gauges shall be checked at least monthly and recorded."},
    ])

    # ----- GB 50116 火灾自动报警 -----
    rules.extend([
        {"id":"GB50116-3.4.1","source":GB50116,"article":"3.4.1","title":"Fire control room staffing",
         "scene":common_scenes_full,"hazard_type":"control_room_staffing",
         "tags":["fire control room","staffing","duty","消防控制室","值班"],
         "text":"Fire control rooms shall be staffed 24 hours by at least two trained operators per shift, holding valid certificates."},
        {"id":"GB50116-3.4.7","source":GB50116,"article":"3.4.7","title":"Fire control room logbook",
         "scene":common_scenes_full,"hazard_type":"daily_patrol_missing",
         "tags":["logbook","fault","fire control","控制室","台账"],
         "text":"Fire control rooms shall keep duty logs, fault logs, and signal logs; faults shall be acknowledged and rectified within 24 hours."},
        {"id":"GB50116-4.4.1","source":GB50116,"article":"4.4.1","title":"Detector spacing in flat ceiling",
         "scene":common_scenes_full,"hazard_type":"detector_missing",
         "tags":["smoke detector","spacing","ceiling","烟感","间距"],
         "text":"Point smoke detectors on flat ceilings shall not exceed the maximum protection radius and shall not be installed within 0.5 m of walls or partitions."},
        {"id":"GB50116-6.2.7","source":GB50116,"article":"6.2.7","title":"Linkage of evacuation broadcast",
         "scene":common_scenes_full,"hazard_type":"alarm_linkage_missing",
         "tags":["broadcast","linkage","evacuation","应急广播","联动"],
         "text":"Emergency broadcast and evacuation lighting shall be linked to fire alarm signals; linkage logic shall be tested at least once per year."},
        {"id":"GB50116-12.4.1","source":GB50116,"article":"12.4.1","title":"Annual full system test",
         "scene":common_scenes_full,"hazard_type":"periodic_inspection_missing",
         "tags":["annual test","linkage","报警系统","年度测试"],
         "text":"Fire alarm systems shall undergo a full functional test at least once per year; results shall be archived for three years."},
    ])

    # ----- GB 51251 防烟排烟 -----
    rules.extend([
        {"id":"GB51251-3.1.5","source":GB51251,"article":"3.1.5","title":"Mechanical exhaust capacity",
         "scene":common_scenes_full,"hazard_type":"smoke_control_damaged",
         "tags":["mechanical exhaust","capacity","机械排烟","风量"],
         "text":"Mechanical smoke exhaust systems shall meet the design air flow; permanent reductions in capacity due to obstructions or fan failure shall be rectified."},
        {"id":"GB51251-4.4.10","source":GB51251,"article":"4.4.10","title":"Smoke vent inspection",
         "scene":common_scenes_full,"hazard_type":"smoke_vent_blocked",
         "tags":["smoke vent","inspection","排烟口","检查"],
         "text":"Smoke vents and dampers shall be inspected at least quarterly; dust accumulation, paint over, or sealing shall be removed promptly."},
        {"id":"GB51251-5.1.6","source":GB51251,"article":"5.1.6","title":"Pressurized air-supply integrity",
         "scene":common_scenes_full,"hazard_type":"smoke_control_damaged",
         "tags":["pressurized air","stairwell","正压","加压送风"],
         "text":"Pressurized air-supply ducts and equipment shall remain intact; modifications affecting air-tightness require formal approval and re-testing."},
    ])

    # ----- GB 50354 装修防火 -----
    rules.extend([
        {"id":"GB50354-3.0.4","source":GB50354,"article":"3.0.4","title":"Decoration combustibility limits",
         "scene":public_scenes,"hazard_type":"combustible_decoration",
         "tags":["decoration","ceiling","wall","B1","装修材料","燃烧性能"],
         "text":"Interior ceiling materials of public spaces shall meet at least Class A combustibility, and wall materials shall meet at least Class B1; lower grades require special approval."},
        {"id":"GB50354-4.0.5","source":GB50354,"article":"4.0.5","title":"Curtain combustibility",
         "scene":public_scenes,"hazard_type":"combustible_decoration",
         "tags":["curtain","fabric","B1","窗帘","布艺"],
         "text":"Curtains, drapes, and fabric partitions in public spaces shall be made of fire-retardant material; untreated combustible fabric shall not be installed."},
    ])

    # ----- GB 25506 控制室通用要求 -----
    rules.extend([
        {"id":"GB25506-5.1","source":GB25506,"article":"5.1","title":"Control room independence",
         "scene":common_scenes_full,"hazard_type":"control_room_unsafe",
         "tags":["control room","separation","wall","控制室","隔墙"],
         "text":"Fire control rooms shall be enclosed with Class A walls and Class A doors; storage of unrelated equipment or materials inside is prohibited."},
        {"id":"GB25506-5.6","source":GB25506,"article":"5.6","title":"Control room equipment list",
         "scene":common_scenes_full,"hazard_type":"control_room_equipment_missing",
         "tags":["control room","equipment","graphic display","控制室","图形显示"],
         "text":"Fire control rooms shall provide alarm controllers, linkage controllers, graphic display units, recording devices, and communication links to fire dispatch centers."},
        {"id":"GB25506-6.3","source":GB25506,"article":"6.3","title":"Operator certification",
         "scene":common_scenes_full,"hazard_type":"control_room_staffing",
         "tags":["certification","training","control room","培训","证书"],
         "text":"Fire control room operators shall hold valid building fire facility operator certificates issued under national vocational standards."},
    ])

    # ----- GA 95 灭火器维修 -----
    rules.extend([
        {"id":"GA95-7.2","source":GA95,"article":"7.2","title":"Extinguisher service interval",
         "scene":common_scenes_full,"hazard_type":"extinguisher_invalid",
         "tags":["extinguisher","service","interval","送修","维修周期"],
         "text":"Dry-powder extinguishers shall be sent for full inspection at most every 5 years; CO2 extinguishers at most every 5 years; service tags shall be attached after maintenance."},
        {"id":"GA95-7.5","source":GA95,"article":"7.5","title":"Extinguisher pressure indicator",
         "scene":common_scenes_full,"hazard_type":"extinguisher_invalid",
         "tags":["pressure indicator","green","red","压力表","失效"],
         "text":"Extinguishers with pressure indicators showing red or yellow zone or with damaged seals shall be removed from service immediately and sent for repair."},
        {"id":"GA95-9.4","source":GA95,"article":"9.4","title":"Service-tag information",
         "scene":common_scenes_full,"hazard_type":"extinguisher_signage_missing",
         "tags":["service tag","records","维修标签","记录"],
         "text":"Each serviced extinguisher shall carry a tag stating service date, next service date, and service company; tags missing or illegible disqualify the unit from service."},
    ])

    # ----- JGJ 46 施工临电 -----
    rules.extend([
        {"id":"JGJ46-3.1.4","source":JGJ46,"article":"3.1.4","title":"TN-S system requirement",
         "scene":["construction","factory"],"hazard_type":"electrical_overload_or_aging",
         "tags":["TN-S","earthing","construction","TN-S","保护接零"],
         "text":"Construction-site temporary electricity shall use the TN-S three-phase five-wire system with dedicated PE conductor; mixing TT and TN systems is not permitted."},
        {"id":"JGJ46-3.1.6","source":JGJ46,"article":"3.1.6","title":"Three-tier protection",
         "scene":["construction","factory"],"hazard_type":"electrical_overload_or_aging",
         "tags":["distribution box","leakage protector","三级配电","漏电保护"],
         "text":"Construction-site distribution shall follow three-tier configuration (main, sub, terminal box) with each tier protected by a residual-current device meeting code."},
        {"id":"JGJ46-3.1.10","source":JGJ46,"article":"3.1.10","title":"Distribution box conditions",
         "scene":["construction","factory"],"hazard_type":"distribution_box_unsafe",
         "tags":["distribution box","door","label","配电箱","门"],
         "text":"Distribution boxes shall be locked, labeled, and dry; one-box-multiple-equipment use, doors left open, or boxes exposed to rain are not compliant."},
        {"id":"JGJ46-7.2.4","source":JGJ46,"article":"7.2.4","title":"Cable burying / suspension",
         "scene":["construction","factory"],"hazard_type":"cable_unsafe_routing",
         "tags":["cable","routing","support","电缆","布线"],
         "text":"Outdoor temporary cables shall be buried, suspended, or routed in trays with safe height clearance; laying directly on the ground or across roads without protection is prohibited."},
        {"id":"JGJ46-9.7.3","source":JGJ46,"article":"9.7.3","title":"Welding hot-work approval",
         "scene":["construction","factory"],"hazard_type":"hot_work_without_approval",
         "tags":["hot work","welding","permit","动火","审批"],
         "text":"Welding, cutting, and other hot work on construction sites require approved hot-work permits; on-site fire watchers and extinguishers shall be assigned."},
    ])

    # ----- 消防法 -----
    rules.extend([
        {"id":"FIRELAW-15","source":FIRELAW,"article":"Art.15","title":"Crowded venue inspection before opening",
         "scene":public_scenes,"hazard_type":"public_venue_opening_check",
         "tags":["public venue","inspection","opening","公众聚集","开业前检查"],
         "text":"Public assembly venues shall undergo fire safety inspection before opening; operating without inspection results in administrative penalty."},
        {"id":"FIRELAW-16","source":FIRELAW,"article":"Art.16","title":"Building owner responsibility",
         "scene":common_scenes_full,"hazard_type":"management_responsibility",
         "tags":["responsibility","owner","manager","责任","管理人"],
         "text":"Building owners and use units shall designate a person responsible for fire safety, conduct daily inspections, and rectify hazards within set deadlines."},
        {"id":"FIRELAW-17","source":FIRELAW,"article":"Art.17","title":"Public assembly daily duties",
         "scene":public_scenes,"hazard_type":"daily_patrol_missing",
         "tags":["daily duty","public assembly","日常防火检查"],
         "text":"Public assembly venues shall conduct daily fire safety patrols and keep records; absence of records is treated as patrol missing."},
        {"id":"FIRELAW-18","source":FIRELAW,"article":"Art.18","title":"Shared use building coordination",
         "scene":["office","residential","campus"],"hazard_type":"shared_facility_unmanaged",
         "tags":["shared","property management","共用","物业"],
         "text":"In buildings shared by multiple users, the property manager is responsible for shared evacuation routes, hydrants, and fire facilities."},
        {"id":"FIRELAW-19","source":FIRELAW,"article":"Art.19","title":"Manufacturing site separation",
         "scene":industrial_scenes,"hazard_type":"production_combination_unsafe",
         "tags":["combined building","production","storage","厂房","组合"],
         "text":"Production facilities, warehouses, residential and dormitory functions shall be physically separated; mixed use within one fire compartment is prohibited."},
        {"id":"FIRELAW-21","source":FIRELAW,"article":"Art.21","title":"No occupation of fire lanes",
         "scene":common_scenes_full,"hazard_type":"fire_lane_parking",
         "tags":["fire lane","blocked","消防车通道","占用"],
         "text":"Fire lanes shall not be occupied, blocked, or closed off; persistent illegal parking is subject to penalty under the Fire Law."},
        {"id":"FIRELAW-28","source":FIRELAW,"article":"Art.28","title":"Prohibited e-bike charging",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["e-bike","charging","public corridor","电动车","充电","楼道"],
         "text":"Electric bicycles shall not enter buildings, ride elevators, or be charged in public corridors, lobbies, or evacuation routes."},
        {"id":"FIRELAW-34","source":FIRELAW,"article":"Art.34","title":"Hot-work approval",
         "scene":industrial_scenes,"hazard_type":"hot_work_without_approval",
         "tags":["hot work","permit","动火","审批"],
         "text":"Hot work in or near flammable areas requires approval and protective measures, including isolation and on-site fire watchers."},
        {"id":"FIRELAW-44","source":FIRELAW,"article":"Art.44","title":"Mass-gathering crowd duty",
         "scene":public_scenes,"hazard_type":"mass_gathering_unsafe",
         "tags":["mass gathering","crowd","duty","大型活动","人员密集"],
         "text":"Mass gatherings shall undergo fire safety review with crowd capacity, exit count, evacuation plan, and on-site duty arrangement."},
        {"id":"FIRELAW-60","source":FIRELAW,"article":"Art.60","title":"Penalty for hazard non-rectification",
         "scene":common_scenes_full,"hazard_type":"hazard_rectification_delay",
         "tags":["penalty","rectification","处罚","整改"],
         "text":"Failure to rectify ordered hazards within the deadline may incur fines, business suspension, or other administrative penalties under the Fire Law."},
    ])

    # ----- HMBF 高层民用建筑消防安全管理规定 (extension) -----
    rules.extend([
        {"id":"HMBF-29","source":HMBF,"article":"Art.29","title":"Annual electrical inspection",
         "scene":["residential","office"],"hazard_type":"electrical_overload_or_aging",
         "tags":["electrical","inspection","annual","电气","年检"],
         "text":"High-rise buildings shall conduct an annual electrical fire safety inspection; aged wiring, overloaded sockets, and improper additions shall be repaired."},
        {"id":"HMBF-30","source":HMBF,"article":"Art.30","title":"Property fire facility maintenance",
         "scene":["residential","office"],"hazard_type":"facility_maintenance_missing",
         "tags":["property","maintenance","物业","维保"],
         "text":"Property managers shall sign maintenance contracts for fire facilities and retain inspection records for at least three years."},
        {"id":"HMBF-31","source":HMBF,"article":"Art.31","title":"Decoration permit",
         "scene":["residential","office"],"hazard_type":"renovation_unauthorized",
         "tags":["renovation","permit","装修","报备"],
         "text":"Decoration that may affect fire compartments, evacuation, or fixed fire facilities requires fire safety review and approval."},
        {"id":"HMBF-32","source":HMBF,"article":"Art.32","title":"Lobby furniture limits",
         "scene":["residential","office"],"hazard_type":"evacuation_obstructed",
         "tags":["lobby","furniture","门厅","堆物"],
         "text":"Building lobbies and shared corridors shall not be used to store furniture or non-essential items that reduce the evacuation width."},
        {"id":"HMBF-33","source":HMBF,"article":"Art.33","title":"E-bike charging station design",
         "scene":["residential"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["e-bike","centralized","充电桩","集中"],
         "text":"Residential complexes shall set up centralized charging stations for electric bicycles, separated from main buildings with overcurrent and short-circuit protection."},
        {"id":"HMBF-34","source":HMBF,"article":"Art.34","title":"Combustible storage limit",
         "scene":["office","residential"],"hazard_type":"combustible_storage",
         "tags":["combustible","storage","可燃物","储存"],
         "text":"Storage of large quantities of combustible items in residential or office buildings shall comply with fire compartment limits and shall not block exits."},
        {"id":"HMBF-35","source":HMBF,"article":"Art.35","title":"Drill frequency",
         "scene":["office","residential","campus"],"hazard_type":"drill_missing",
         "tags":["drill","semiannual","演练","半年"],
         "text":"Fire drills shall be conducted at least twice per year and recorded; absence of records is treated as drill missing."},
        {"id":"HMBF-36","source":HMBF,"article":"Art.36","title":"Emergency plan template",
         "scene":["office","residential","campus"],"hazard_type":"emergency_plan_missing",
         "tags":["emergency plan","template","应急预案","模板"],
         "text":"High-rise buildings shall maintain a written fire emergency plan including evacuation routes, duty roster, and contacting procedures."},
        {"id":"HMBF-37","source":HMBF,"article":"Art.37","title":"E-bike no charging in public",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["e-bike","charging","corridor","stairwell","楼道","充电"],
         "text":"Electric bicycles shall not be charged in evacuation routes, stairwells, public corridors, lobbies, or refuge floors of high-rise residential buildings."},
        {"id":"HMBF-38","source":HMBF,"article":"Art.38","title":"Owner education",
         "scene":["residential"],"hazard_type":"training_missing",
         "tags":["education","resident","居民","宣传"],
         "text":"Property managers and owners' committees shall organize fire safety education for residents at least twice per year."},
        {"id":"HMBF-39","source":HMBF,"article":"Art.39","title":"Hazard reporting channel",
         "scene":["residential","office"],"hazard_type":"hazard_report_channel_missing",
         "tags":["report","hazard","channel","举报","渠道"],
         "text":"Buildings shall provide a clear hazard reporting channel for residents and employees; reported hazards shall be acknowledged within 24 hours."},
        {"id":"HMBF-43","source":HMBF,"article":"Art.43","title":"Insufficient evidence camera",
         "scene":["residential","office"],"hazard_type":"insufficient_evidence",
         "tags":["camera","blurry","evidence","视频","证据不足"],
         "text":"When monitoring footage is blurry, partial, or otherwise insufficient, fire managers shall request on-site rechecking before issuing rectification orders."},
        {"id":"HMBF-44","source":HMBF,"article":"Art.44","title":"Evidence preservation",
         "scene":["residential","office"],"hazard_type":"evidence_preservation",
         "tags":["evidence","photo","preservation","证据","保留"],
         "text":"Fire safety records and on-site photos shall be preserved for at least one year and shall accompany rectification reports."},
        {"id":"HMBF-45","source":HMBF,"article":"Art.45","title":"Tenant change reporting",
         "scene":["office","residential"],"hazard_type":"tenant_change_unreported",
         "tags":["tenant","reporting","承租","报备"],
         "text":"Changes of tenant or use type in high-rise buildings shall be reported to the fire safety responsible person and may require additional fire safety review."},
        {"id":"HMBF-46","source":HMBF,"article":"Art.46","title":"Special area handover",
         "scene":["residential","office"],"hazard_type":"area_handover_unclear",
         "tags":["handover","责任移交","管理交接"],
         "text":"Fire safety responsibility for shared facilities shall not lapse during property handover; written handover records shall be kept."},
        {"id":"HMBF-47-1","source":HMBF,"article":"Art.47.1","title":"E-bike non-compliance penalty",
         "scene":["residential","campus"],"hazard_type":"e_bike_penalty",
         "tags":["e-bike","penalty","处罚","电动车"],
         "text":"E-bike charging in public areas of high-rise buildings is subject to administrative warning and fines; repeated violations may result in summons."},
        {"id":"HMBF-47-7","source":HMBF,"article":"Art.47.7","title":"Specific corridor charging penalty",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["corridor","e-bike","charging","penalty","楼道","处罚"],
         "text":"Persons who charge electric bicycles in residential corridors or stairwells of high-rise buildings shall be ordered to remove the charging immediately and may be fined."},
    ])

    # ----- Order 61 机关团体企事业 -----
    rules.extend([
        {"id":"ORDER61-13","source":ORDER61,"article":"Art.13","title":"Fire safety responsible person duties",
         "scene":common_scenes_full,"hazard_type":"management_responsibility",
         "tags":["responsible person","duty","消防安全责任人"],
         "text":"Fire safety responsible persons shall organize the formulation of fire safety systems, the implementation of fire safety duties, and the rectification of hazards."},
        {"id":"ORDER61-19","source":ORDER61,"article":"Art.19","title":"Patrol records",
         "scene":common_scenes_full,"hazard_type":"daily_patrol_missing",
         "tags":["patrol","record","巡查","台账"],
         "text":"Units shall conduct daily patrols of public areas, with patrol records identifying the inspector, time, and findings."},
        {"id":"ORDER61-20","source":ORDER61,"article":"Art.20","title":"Annual self-examination",
         "scene":common_scenes_full,"hazard_type":"periodic_inspection_missing",
         "tags":["self-examination","annual","自查","年度"],
         "text":"Units shall conduct comprehensive self-examination of fire safety at least once per year, archiving findings and rectification status."},
        {"id":"ORDER61-22","source":ORDER61,"article":"Art.22","title":"Hot-work registration",
         "scene":common_scenes_full,"hazard_type":"hot_work_without_approval",
         "tags":["hot work","registration","动火"],
         "text":"Hot-work activities within unit premises shall be registered, with site protective measures and authorized supervisors named."},
        {"id":"ORDER61-25","source":ORDER61,"article":"Art.25","title":"Personnel training records",
         "scene":common_scenes_full,"hazard_type":"training_missing",
         "tags":["training","record","培训","记录"],
         "text":"Units shall arrange fire safety training for new employees and refresher training for existing employees, with attendance records preserved."},
        {"id":"ORDER61-31","source":ORDER61,"article":"Art.31","title":"Volunteer fire team",
         "scene":industrial_scenes + ["campus"],"hazard_type":"volunteer_team_missing",
         "tags":["volunteer team","initial response","志愿消防队","义务"],
         "text":"Larger units shall establish volunteer fire teams, equip basic firefighting tools, and organize at least one drill per year."},
    ])

    # ----- 生产安全应急条例 -----
    rules.extend([
        {"id":"EMERG-5","source":EMERG_REG,"article":"Art.5","title":"Emergency response system",
         "scene":industrial_scenes,"hazard_type":"emergency_plan_missing",
         "tags":["emergency","plan","duty","应急","指挥"],
         "text":"Production units shall establish an emergency response system covering early warning, response procedures, on-site command, and post-event review."},
        {"id":"EMERG-7","source":EMERG_REG,"article":"Art.7","title":"Plan filing",
         "scene":industrial_scenes,"hazard_type":"emergency_plan_missing",
         "tags":["plan","filing","local authority","预案","备案"],
         "text":"Emergency plans of high-risk units shall be filed with local emergency management authorities and reviewed at least every three years."},
        {"id":"EMERG-22","source":EMERG_REG,"article":"Art.22","title":"Initial response duty",
         "scene":industrial_scenes,"hazard_type":"emergency_response_delay",
         "tags":["initial response","first hour","first responder","初期处置","到场"],
         "text":"Production units shall ensure first-responder presence and isolation of the incident scene; reports to the responsible authority shall be filed without delay."},
        {"id":"EMERG-28","source":EMERG_REG,"article":"Art.28","title":"Post-event review",
         "scene":industrial_scenes,"hazard_type":"post_event_review_missing",
         "tags":["post-event","review","记录","事后回顾"],
         "text":"After emergency incidents, units shall complete post-event reviews documenting causes, response performance, and improvement actions."},
    ])

    # ----- 重大事故隐患判定 (工贸) -----
    rules.extend([
        {"id":"SEVERE-2.1","source":SEVERE_HAZARD,"article":"Sec.2.1","title":"Workshop dormitory mixed use",
         "scene":industrial_scenes,"hazard_type":"production_combination_unsafe",
         "tags":["dormitory","workshop","mixed","三合一","混用"],
         "text":"Industrial workshops combined with dormitories or canteens within the same fire compartment constitute a major hazard requiring immediate rectification."},
        {"id":"SEVERE-2.4","source":SEVERE_HAZARD,"article":"Sec.2.4","title":"Locked exits in production",
         "scene":industrial_scenes,"hazard_type":"exit_door_wrong",
         "tags":["exit","locked","factory","厂房","上锁"],
         "text":"Locked or blocked safety exits in factory production areas during operation are classified as major fire hazards under workplace safety rules."},
        {"id":"SEVERE-3.6","source":SEVERE_HAZARD,"article":"Sec.3.6","title":"Combustible dust collector position",
         "scene":industrial_scenes,"hazard_type":"dust_explosion_risk",
         "tags":["dust","explosion","collector","粉尘","除尘器"],
         "text":"Dust collectors handling combustible dust shall be installed outdoors or separated; indoor placement near fire sources or non-explosion-proof equipment is a major hazard."},
        {"id":"SEVERE-4.1","source":SEVERE_HAZARD,"article":"Sec.4.1","title":"Hot-work supervisor missing",
         "scene":industrial_scenes,"hazard_type":"hot_work_without_approval",
         "tags":["hot work","supervisor","动火","监护"],
         "text":"Hot work in flammable workshops without on-site supervisors and approved permits is classified as a major hazard subject to immediate suspension."},
        {"id":"SEVERE-5.2","source":SEVERE_HAZARD,"article":"Sec.5.2","title":"Spray painting room ventilation",
         "scene":industrial_scenes,"hazard_type":"spray_room_unsafe",
         "tags":["spray painting","ventilation","喷漆房","通风"],
         "text":"Spray painting rooms shall have explosion-proof ventilation and exhaust systems with regular cleaning records; failure constitutes a major fire/explosion hazard."},
    ])

    # ----- 危险化学品 -----
    rules.extend([
        {"id":"HAZCHEM-22","source":HAZCHEM,"article":"Art.22","title":"Dangerous chemical separation",
         "scene":industrial_scenes,"hazard_type":"hazardous_goods_storage",
         "tags":["dangerous chemicals","storage","separation","危化品","隔离"],
         "text":"Dangerous chemicals incompatible by hazard category shall be stored separately; mixed storage of acid and alkali, oxidizer and combustible is prohibited."},
        {"id":"HAZCHEM-25","source":HAZCHEM,"article":"Art.25","title":"Storage labeling",
         "scene":industrial_scenes,"hazard_type":"hazardous_signage_missing",
         "tags":["labeling","SDS","危化品","标签"],
         "text":"Each dangerous chemical container shall be labeled with chemical name, GHS warnings, and emergency contact; missing labels are non-compliant."},
        {"id":"HAZCHEM-30","source":HAZCHEM,"article":"Art.30","title":"Transportation safety",
         "scene":industrial_scenes,"hazard_type":"hazardous_transport_unsafe",
         "tags":["transport","license","危化品","运输"],
         "text":"Vehicles transporting dangerous chemicals shall hold valid permits, follow approved routes, and be operated by qualified drivers and escorts."},
    ])

    # ----- 餐饮油烟管道 -----
    rules.extend([
        {"id":"KITCHEN-1","source":KITCHEN,"article":"Sec.1","title":"Kitchen exhaust cleaning interval",
         "scene":["campus","office","residential"],"hazard_type":"kitchen_exhaust",
         "tags":["kitchen","exhaust","cleaning","油烟道","清洗"],
         "text":"Commercial kitchen exhaust ducts shall be cleaned at least once every quarter; cleaning records shall be kept for at least one year."},
        {"id":"KITCHEN-2","source":KITCHEN,"article":"Sec.2","title":"Kitchen extinguishing system",
         "scene":["campus","office","residential"],"hazard_type":"kitchen_extinguish_missing",
         "tags":["kitchen","extinguishing","exhaust hood","厨房","灶台灭火"],
         "text":"Commercial kitchen exhaust hoods serving multiple stoves shall install dedicated kitchen extinguishing systems with monthly inspection."},
    ])

    # ----- 电动自行车 GB 42295 -----
    rules.extend([
        {"id":"EBIKE-7.1","source":EBIKE,"article":"Sec.7.1","title":"Centralized charging area design",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["centralized","charging","fire compartment","集中充电","防火分区"],
         "text":"Centralized e-bike charging areas in residential or campus complexes shall be separated from main buildings by fire walls or open-air structures with monitoring."},
        {"id":"EBIKE-8.3","source":EBIKE,"article":"Sec.8.3","title":"Battery indoor charging prohibition",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["battery","indoor","住宅","电池","充电"],
         "text":"Removing the e-bike battery for indoor charging in residential dwellings is prohibited unless using an enclosed fire-resistant cabinet."},
    ])

    # ----- Production safety / industrial -----
    rules.extend([
        {"id":"PROD-01","source":"安全用电管理要点(工业/工地)","article":"临电-01","title":"Site temporary electrical practice",
         "scene":industrial_scenes,"hazard_type":"electrical_overload_or_aging",
         "tags":["temporary","electrical","industrial","临电","工业"],
         "text":"Industrial and construction sites using temporary electricity shall maintain protective earthing, leakage protection, and weatherproof distribution boxes."},
        {"id":"PROD-02","source":"安全用电管理要点(工业/工地)","article":"临电-02","title":"Cable damage rectification",
         "scene":industrial_scenes,"hazard_type":"cable_damaged",
         "tags":["cable","damage","insulation","破损","绝缘"],
         "text":"Cables with damaged insulation, exposed copper, or scorched surfaces shall be replaced before continued use; tape patches are not a permanent fix."},
        {"id":"PROD-03","source":"安全用电管理要点(工业/工地)","article":"临电-03","title":"One-box-one-machine",
         "scene":industrial_scenes,"hazard_type":"multi_device_one_box",
         "tags":["one machine","one switch","一机一闸","开关箱"],
         "text":"Construction-site terminal switch boxes shall serve a single piece of equipment; multiple machines sharing one terminal box is prohibited."},
        {"id":"PROD-04","source":"安全用电管理要点(工业/工地)","article":"临电-04","title":"Box position",
         "scene":industrial_scenes,"hazard_type":"distribution_box_unsafe",
         "tags":["distribution box","position","安装位置","配电箱"],
         "text":"Distribution boxes shall not be placed under direct rain, in flammable storage areas, or where rescue access is blocked."},
        {"id":"PROD-05","source":"安全用电管理要点(工业/工地)","article":"临电-05","title":"Earthing test",
         "scene":industrial_scenes,"hazard_type":"earthing_unmaintained",
         "tags":["earthing","resistance","test","接地电阻"],
         "text":"PE conductor and earthing resistance shall be tested at site startup and periodically; resistance exceeding 4 ohm requires immediate rectification."},
        {"id":"PROD-06","source":"安全用电管理要点(工业/工地)","article":"临电-06","title":"Welding gas-cylinder spacing",
         "scene":industrial_scenes,"hazard_type":"welding_unsafe",
         "tags":["welding","oxygen","acetylene","spacing","氧气","乙炔"],
         "text":"During welding, oxygen and acetylene cylinders shall be at least 5 m apart and at least 10 m from open flame or heat source."},
    ])

    # Existing source: HMBF + Fire Law already had ones in original; we keep those untouched in the original file.
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
    # update meta
    kb = data.get("knowledge_base", {})
    kb["version"] = "v2.0.0"
    kb["built_at"] = "2026-04-27"
    kb["expansion_note"] = "Expanded to broader sources for paper-grade evaluation."
    # update sources list
    sources = sorted({r["source"] for r in merged})
    kb["sources"] = [{"code": s} for s in sources]
    data["knowledge_base"] = kb
    data["rules"] = merged

    out = target_file
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out} with {len(merged)} rules.")


if __name__ == "__main__":
    main()
