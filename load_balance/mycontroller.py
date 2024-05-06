#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections

def writeFristRules(p4info_helper, index, ingress_sw):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": ("10.0.0.1" if index == 1 else "10.0.0.2", 32)
        },
        action_name="MyIngress.set_ecmp_select",
        action_params={
            "ecmp_base": 0,
            "ecmp_count": 4
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": ("10.0.1.1" if index == 1 else "10.0.2.2", 32)
        },
        action_name="MyIngress.set_ecmp_select",
        action_params={
            "ecmp_base": 4,
            "ecmp_count": 1
        })
    ingress_sw.WriteTableEntry(table_entry)

    for i in range(0, 4):
        table_entry = p4info_helper.buildTableEntry(
            table_name="MyIngress.ecmp_nhop",
            match_fields={
                "meta.ecmp_select": i
            },
            action_name="MyIngress.set_nhop",
            action_params={
                "nhop_dmac": "00:00:00:00:0" + str(index) + ":0" + str(2 + i),
                "nhop_ipv4": "10.0.2.2" if index == 1 else "10.0.1.1",
	            "port" : 2 + i
            })
        ingress_sw.WriteTableEntry(table_entry)

        table_entry = p4info_helper.buildTableEntry(
            table_name="MyEgress.send_frame",
            match_fields={
                "standard_metadata.egress_port": i + 2
            },
            action_name="MyEgress.rewrite_mac",
            action_params={
                "smac": "00:00:00:0" + str(index) + ":0" + str(i + 2) + ":00"
            })
        ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop",
        match_fields={
            "meta.ecmp_select": 4
        },
        action_name="MyIngress.set_nhop",
        action_params={
            "nhop_dmac": "08:00:00:00:01:01" if index == 1 else "08:00:00:00:02:02",
            "nhop_ipv4": "10.0.2.2" if index == 1 else "10.0.1.1",
	        "port" : 1
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.send_frame",
        match_fields={
            "standard_metadata.egress_port": 1
        },
        action_name="MyEgress.rewrite_mac",
        action_params={
            "smac": "08:00:00:00:01:01" if index == 1 else "08:00:00:00:02:02"
        })
    ingress_sw.WriteTableEntry(table_entry)

def writeRules(p4info_helper, index, ingress_sw):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": ("10.0.1.1", 32)
        },
        action_name="MyIngress.set_ecmp_select",
        action_params={
            "ecmp_base": 0,
            "ecmp_count": 1
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": ("10.0.2.2", 32)
        },
        action_name="MyIngress.set_ecmp_select",
        action_params={
            "ecmp_base": 1,
            "ecmp_count": 1
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop",
        match_fields={
            "meta.ecmp_select": 0
        },
        action_name="MyIngress.set_nhop",
        action_params={
            "nhop_dmac": "00:00:00:00:0"+str(index)+":01",
            "nhop_ipv4": "10.0.1.1",
	        "port" : 1
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.send_frame",
        match_fields={
            "standard_metadata.egress_port": 1
        },
        action_name="MyEgress.rewrite_mac",
        action_params={
            "smac": "00:00:00:0"+str(index)+":01:00"
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop",
        match_fields={
            "meta.ecmp_select": 1
        },
        action_name="MyIngress.set_nhop",
        action_params={
            "nhop_dmac": "00:00:00:00:0"+str(index)+":02",
            "nhop_ipv4": "10.0.2.2",
	        "port" : 2
        })
    ingress_sw.WriteTableEntry(table_entry)

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.send_frame",
        match_fields={
            "standard_metadata.egress_port": 2
        },
        action_name="MyEgress.rewrite_mac",
        action_params={
            "smac": "00:00:00:0"+str(index)+":02:00"
        })
    ingress_sw.WriteTableEntry(table_entry)

def main(p4info_file_path, bmv2_file_path):
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)
    try:
        swlist = []
        for i in range(1, 6):
            swlist.append(p4runtime_lib.bmv2.Bmv2SwitchConnection(
                name='s'+str(i) ,
                address='127.0.0.1:50051',
                device_id=i-1,
                proto_dump_file='logs/s'+str(i)+'-p4runtime-requests.txt'))
            swlist[i-1].MasterArbitrationUpdate()
            swlist[i-1].SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                                    bmv2_json_file_path=bmv2_file_path)

        writeFristRules(p4info_helper, 1, swlist[0])
        writeFristRules(p4info_helper, 6, swlist[5])
        writeRules(p4info_helper, 2, swlist[1])
        writeRules(p4info_helper, 3, swlist[2])
        writeRules(p4info_helper, 4, swlist[3])
        writeRules(p4info_helper, 5, swlist[4])

        while True:
            sleep(2)

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
