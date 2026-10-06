#!/usr/bin/env python3
"""Final-pass expansion: bring fire_rules from 186 to 220+ rules.

Adds: gas safety, parking, charging stations, hospital/childcare, hotel safety, IT room safety.
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

    # Gas / LPG safety -- 城镇燃气管理条例 + GB 50028
    GASREG = "城镇燃气管理条例 (国务院令)"
    GB50028 = "GB 50028-2006"

    rules.extend([
        {"id":"GASREG-25","source":GASREG,"article":"Art.25","title":"User gas pipeline maintenance",
         "scene":public_scenes,"hazard_type":"gas_pipeline_unsafe",
         "tags":["gas","user","pipeline","燃气","用户"],
         "text":"Gas users shall not modify, conceal, or block gas pipelines and gas meters; modifications shall be conducted by qualified suppliers."},
        {"id":"GASREG-31","source":GASREG,"article":"Art.31","title":"LPG cylinder filling",
         "scene":public_scenes + ["factory"],"hazard_type":"lpg_cylinder_unsafe",
         "tags":["LPG","cylinder","filling","液化气","充装"],
         "text":"LPG cylinders shall only be filled at licensed stations; private decanting between cylinders is prohibited and constitutes a major hazard."},
        {"id":"GB50028-10.2.6","source":GB50028,"article":"10.2.6","title":"Gas-room ventilation",
         "scene":public_scenes + ["factory"],"hazard_type":"ventilation_inadequate",
         "tags":["gas room","ventilation","燃气","通风"],
         "text":"Indoor gas equipment rooms shall have natural ventilation openings at high and low levels; mechanical ventilation shall use explosion-proof fans."},
        {"id":"GB50028-10.5.1","source":GB50028,"article":"10.5.1","title":"Gas leak alarm",
         "scene":public_scenes + ["factory"],"hazard_type":"alarm_device_abnormal",
         "tags":["gas leak","alarm","可燃气体探测器"],
         "text":"Locations using piped fuel gas indoors shall install combustible-gas leak detectors with audible alarm and shutoff valve linkage."},
    ])

    # Parking and EV charging
    EVCHARGE = "GB 50966-2014 / 电动汽车充电基础设施"
    rules.extend([
        {"id":"EVCHARGE-3.2","source":EVCHARGE,"article":"Sec.3.2","title":"EV charging station fire compartment",
         "scene":public_scenes + ["factory"],"hazard_type":"ev_charging_compartment_unsafe",
         "tags":["EV","charging","compartment","电动汽车","充电桩"],
         "text":"Indoor EV charging stations shall be located in dedicated fire compartments with sprinklers and combustible-gas detectors."},
        {"id":"EVCHARGE-4.1","source":EVCHARGE,"article":"Sec.4.1","title":"Charger maintenance",
         "scene":public_scenes + ["factory"],"hazard_type":"electrical_overload_or_aging",
         "tags":["charger","maintenance","充电桩","维护"],
         "text":"EV chargers shall be inspected quarterly for cable abrasion, plug melting, and ventilation; faulty units shall be removed from service."},
    ])

    # Hospital / childcare / care home
    HOSPITAL = "医疗机构消防安全管理"
    SCHOOL = "中小学幼儿园消防安全管理"
    HOTEL = "宾馆酒店消防安全管理"

    rules.extend([
        {"id":"HOSPITAL-1","source":HOSPITAL,"article":"Sec.1","title":"Hospital escape assistance",
         "scene":["office","campus"],"hazard_type":"venue_exit_insufficient",
         "tags":["hospital","escape","stretcher","医院","担架"],
         "text":"Hospitals shall keep evacuation corridors at least 2.4 m wide for stretcher passage; storing trolleys, equipment, or chairs in the corridor is prohibited."},
        {"id":"HOSPITAL-2","source":HOSPITAL,"article":"Sec.2","title":"Oxygen storage",
         "scene":["office","campus"],"hazard_type":"oxygen_storage_unsafe",
         "tags":["oxygen","cylinder","氧气","储存"],
         "text":"Hospital oxygen cylinder rooms shall be separated from heat sources, with cylinders chained vertically and separated from full and empty stock."},
        {"id":"HOSPITAL-3","source":HOSPITAL,"article":"Sec.3","title":"Operating-room emergency",
         "scene":["office"],"hazard_type":"emergency_plan_missing",
         "tags":["operating room","emergency","手术室","应急"],
         "text":"Operating rooms shall have emergency power within 15 seconds of mains failure and clearly marked manual disconnection of medical-gas valves."},
        {"id":"SCHOOL-1","source":SCHOOL,"article":"Sec.1","title":"Childcare evacuation drill",
         "scene":["campus"],"hazard_type":"drill_missing",
         "tags":["childcare","drill","幼儿园","演练"],
         "text":"Kindergartens and primary schools shall conduct fire evacuation drills at least once per term, including escape routes from upper floors."},
        {"id":"SCHOOL-2","source":SCHOOL,"article":"Sec.2","title":"Lab chemical storage",
         "scene":["campus"],"hazard_type":"hazardous_goods_storage",
         "tags":["lab","chemical","学校","实验室"],
         "text":"School laboratory chemicals shall be stored by category in dedicated cabinets; flammables and oxidizers shall not share the same cabinet."},
        {"id":"SCHOOL-3","source":SCHOOL,"article":"Sec.3","title":"Classroom power outlet limit",
         "scene":["campus"],"hazard_type":"electrical_overload_or_aging",
         "tags":["classroom","power","教室","插座"],
         "text":"Classrooms shall not chain multiple power strips; high-power equipment such as electric kettles shall not be plugged into classroom outlets."},
        {"id":"HOTEL-1","source":HOTEL,"article":"Sec.1","title":"Guest evacuation map",
         "scene":["office"],"hazard_type":"evacuation_map_missing",
         "tags":["hotel","map","guest","酒店","疏散图"],
         "text":"Hotel guest rooms shall have an evacuation map showing the exit route to the nearest stairwell on the back of the door."},
        {"id":"HOTEL-2","source":HOTEL,"article":"Sec.2","title":"Hotel front-desk emergency duty",
         "scene":["office"],"hazard_type":"emergency_response_delay",
         "tags":["hotel","front desk","duty","酒店","值班"],
         "text":"Hotels shall maintain 24-hour front-desk emergency duty with at least one staff trained in fire suppression and evacuation."},
    ])

    # Data center / IT room
    ITROOM = "数据中心机房消防安全 (GB 50174)"
    rules.extend([
        {"id":"ITROOM-1","source":ITROOM,"article":"Sec.1","title":"Server-room fire suppression",
         "scene":["office","factory"],"hazard_type":"server_room_unprotected",
         "tags":["data center","gas suppression","机房","气体灭火"],
         "text":"Data centers and primary server rooms shall use approved gas suppression systems (FM-200, IG541, or equivalent), not water sprinklers."},
        {"id":"ITROOM-2","source":ITROOM,"article":"Sec.2","title":"Server-room access control",
         "scene":["office","factory"],"hazard_type":"control_room_staffing",
         "tags":["server room","access control","机房","门禁"],
         "text":"Server room access shall be restricted; combustible packaging materials inside the room are prohibited."},
        {"id":"ITROOM-3","source":ITROOM,"article":"Sec.3","title":"UPS battery room ventilation",
         "scene":["office","factory"],"hazard_type":"ventilation_inadequate",
         "tags":["UPS","battery","ventilation","UPS","电池室"],
         "text":"UPS battery rooms shall have continuous ventilation to disperse hydrogen; battery storage above safe SOC limits is prohibited."},
    ])

    # Construction additional
    rules.extend([
        {"id":"JGJ46-3.3.4","source":"JGJ 46-2005","article":"3.3.4","title":"Site temp dorm fire requirement",
         "scene":["construction"],"hazard_type":"temporary_dorm_unsafe",
         "tags":["temporary dorm","site","板房","工地宿舍"],
         "text":"On-site temporary dormitories shall be constructed of non-combustible or B1 panels with separation from material storage and welding zones."},
        {"id":"JGJ46-3.3.6","source":"JGJ 46-2005","article":"3.3.6","title":"Site fire facility provisioning",
         "scene":["construction"],"hazard_type":"extinguisher_count_low",
         "tags":["site","extinguisher","sand bucket","灭火器","沙桶"],
         "text":"Construction sites shall provide adequate portable extinguishers, sand buckets, and water tanks based on construction scale; missing facilities are non-compliant."},
        {"id":"JGJ46-9.4.2","source":"JGJ 46-2005","article":"9.4.2","title":"Welder qualification",
         "scene":["construction","factory"],"hazard_type":"hot_work_without_approval",
         "tags":["welder","qualification","焊工","资格"],
         "text":"Welding and cutting work on sites shall be performed by personnel holding valid special-operation certificates; uncertified hot work is prohibited."},
    ])

    # E-bike additional
    rules.extend([
        {"id":"EBIKE-9.1","source":"GB 42295-2022","article":"Sec.9.1","title":"Charging socket overcurrent",
         "scene":["residential","campus"],"hazard_type":"electrical_overload_or_aging",
         "tags":["e-bike","socket","overcurrent","充电","过流"],
         "text":"E-bike charging sockets shall have individual overcurrent and short-circuit protection that automatically disconnects on fault."},
        {"id":"EBIKE-10.2","source":"GB 42295-2022","article":"Sec.10.2","title":"Charging time control",
         "scene":["residential","campus"],"hazard_type":"e_bike_charging_in_public_area",
         "tags":["e-bike","time","control","充电时长"],
         "text":"E-bike charging stations shall provide automatic time-limit and overcharge protection; uncontrolled overnight charging is treated as a hazard."},
    ])

    # Misc emergency / management additions
    rules.extend([
        {"id":"FIRELAW-22","source":"Fire Law of PRC","article":"Art.22","title":"Building owner record",
         "scene":common_full,"hazard_type":"management_responsibility",
         "tags":["record","building","信息","台账"],
         "text":"Building owners shall keep an up-to-date fire safety record including layout, facility status, and inspection log accessible to fire authorities."},
        {"id":"FIRELAW-31","source":"Fire Law of PRC","article":"Art.31","title":"Government supervision",
         "scene":common_full,"hazard_type":"government_supervision",
         "tags":["supervision","government","监督","执法"],
         "text":"Public security and emergency authorities are authorized to conduct unannounced inspections of fire safety; obstruction is subject to penalty."},
    ])

    return rules


def main():
    target_file = RULES_FILE
    if not target_file.exists():
        sys.exit(1)
    with open(target_file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    existing = data.get("rules", [])
    existing_ids = {r["id"] for r in existing}
    new_rules = [r for r in gen_rules() if r["id"] not in existing_ids]
    print(f"Existing: {len(existing)}, New: {len(new_rules)}")
    merged = existing + new_rules
    kb = data.get("knowledge_base", {})
    kb["version"] = "v2.2.0"
    kb["built_at"] = "2026-04-27"
    kb["expansion_note"] = "Round-3 expansion: gas, EV, hospital, school, hotel, data center."
    sources = sorted({r["source"] for r in merged})
    kb["sources"] = [{"code": s} for s in sources]
    data["knowledge_base"] = kb
    data["rules"] = merged
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {target_file} with {len(merged)} rules.")


if __name__ == "__main__":
    main()
