import base64
import json
from dataclasses import replace
from pathlib import Path
import sys
import time

import pytest

from tb4.discovery_catalogue import DiscoveryError, Interface, Observation, Scope
from tb4.discovery_native import (BoundedRead, NativeNeighbors, collect_neighbors,
                                  collect_fixed, decoded, MAX_OUTPUT)
from test_catalogue import POLICY, observed


class Runner:
    def __init__(self, responses):
        self.responses=list(responses);self.calls=[]
    def run(self,argv,*,timeout):
        self.calls.append((argv,timeout))
        value=self.responses.pop(0)
        if isinstance(value,Exception):raise value
        return json.dumps(value).encode()


def linux_runner(*, after=None, rows=None):
    iface=[dict(ifindex=7,ifname="synthetic-lan")]
    return Runner([iface, rows if rows is not None else [
        dict(dst="192.0.2.8",lladdr="00:11:22:33:44:55"),
        dict(dst="203.0.113.8",lladdr="00:11:22:33:44:66")],iface if after is None else after])


def local_policy():
    return replace(POLICY,interfaces=(POLICY.interfaces[0],))


def port(runner,platform="linux"):
    return NativeNeighbors(platform=platform,program=str(Path(sys.executable)),runner=runner)


def test_linux_commands_are_interface_selected_and_out_of_scope_rows_discarded():
    runner=linux_runner()
    result=collect_neighbors(local_policy(),port(runner),clock=lambda:100)
    assert result.status=="COMPLETE" and len(result.observations)==1
    assert result.observations[0].address=="192.0.2.8"
    assert not result.observations[0].online
    assert [c[0][1:] for c in runner.calls]==[
        ("-j","link","show","dev","synthetic-lan"),
        ("-j","neigh","show","dev","synthetic-lan"),
        ("-j","link","show","dev","synthetic-lan")]
    assert all(0 < call[1] <= 5 for call in runner.calls)


@pytest.mark.parametrize("after", [[],[dict(ifindex=8,ifname="synthetic-lan")],
                                  [dict(ifindex=7,ifname="other-interface")]])
def test_changed_interface_discards_entire_collection(after):
    result=collect_neighbors(local_policy(),port(linux_runner(after=after)),clock=lambda:100)
    assert result.status=="UNAVAILABLE" and not result.observations


def test_initial_interface_mismatch_never_queries_neighbor_cache():
    runner=Runner([[dict(ifindex=8,ifname="synthetic-lan")]])
    result=collect_neighbors(local_policy(),port(runner),clock=lambda:100)
    assert result.status=="UNAVAILABLE" and len(runner.calls)==1


def test_windows_script_only_interpolates_integer_and_checks_exact_current_alias():
    interface=Interface("synthetic '; $private = 1",7,("192.0.2.0/24",),"LAN")
    iface=[dict(InterfaceIndex=7,InterfaceAlias=interface.name)]
    neighbors=[dict(InterfaceIndex=7,InterfaceAlias=interface.name,IPAddress="192.0.2.8",
                    LinkLayerAddress="00-11-22-33-44-55")]
    runner=Runner([iface,neighbors,iface]); native=port(runner,"win32")
    result=collect_neighbors(Scope((interface,)),native,clock=lambda:100)
    assert result.status=="COMPLETE" and result.observations[0].hardware_hint=="00:11:22:33:44:55"
    for argv,_ in runner.calls:
        assert argv[1:5]==("-NoLogo","-NoProfile","-NonInteractive","-EncodedCommand")
        script=base64.b64decode(argv[-1]).decode("utf-16-le")
        assert "-InterfaceIndex 7" in script and interface.name not in script
        assert "IncludeAllCompartments" not in script and "CimSession" not in script


def test_wrong_windows_neighbor_index_never_enters_observations():
    iface=[dict(InterfaceIndex=7,InterfaceAlias="synthetic-lan")]
    runner=Runner([iface,[dict(InterfaceIndex=8,InterfaceAlias="synthetic-lan",
                              IPAddress="192.0.2.8",LinkLayerAddress="aa-bb")]])
    result=collect_neighbors(local_policy(),port(runner,"win32"),clock=lambda:100)
    assert result.status=="UNAVAILABLE" and not result.observations


def test_broadcast_multicast_and_zero_address_never_create_devices():
    rows=[dict(dst=ip,lladdr="00:11") for ip in
          ("192.0.2.255","255.255.255.255","224.0.0.1","0.0.0.0")]
    result=collect_neighbors(local_policy(),port(linux_runner(rows=rows)),clock=lambda:100)
    assert result.status=="COMPLETE" and not result.observations


def test_empty_scope_and_disabled_method_never_call_os():
    runner=Runner([]);native=port(runner)
    assert collect_neighbors(Scope(()),native,clock=lambda:100).status=="ISOLATED"
    assert collect_neighbors(replace(local_policy(),methods=frozenset({"ICMP"})),
                             native,clock=lambda:100).status=="METHOD_UNQUALIFIED"
    assert not runner.calls


def test_collection_overflow_preserves_no_partial_candidate():
    rows=[dict(dst="192.0.2."+str(i),lladdr="synthetic") for i in (8,9)]
    result=collect_neighbors(replace(local_policy(),max_observations=1),
                             port(linux_runner(rows=rows)),clock=lambda:100)
    assert result.status=="OVERFLOW" and not result.observations


def test_total_deadline_refuses_remaining_queries():
    ticks=iter([0,16])
    runner=Runner([])
    result=collect_neighbors(local_policy(),port(runner),clock=lambda:100,monotonic=lambda:next(ticks))
    assert result.status=="UNAVAILABLE" and not runner.calls


@pytest.mark.parametrize("raw",[b'{}',b'[{"a":1,"a":2}]',b'[NaN]',b'[',
                                b'X'*(MAX_OUTPUT+1),json.dumps([{}]*257).encode()],
                         ids=["wrong-shape","duplicate-key","nonfinite","truncated","too-large","too-many-rows"])
def test_closed_bounded_provider_json(raw):
    with pytest.raises(DiscoveryError):
        decoded(raw)


def test_provider_errors_and_repr_are_closed(capsys):
    runner=Runner([RuntimeError("SYNTHETIC_PRIVATE_CANARY")])
    result=collect_neighbors(local_policy(),port(runner),clock=lambda:100)
    assert result.summary()==dict(status="UNAVAILABLE",observed=0,completed_queries=0,failed_queries=1)
    assert "CANARY" not in repr(result)+json.dumps(result.summary())
    assert capsys.readouterr()==("","")


def test_fixed_helper_targets_are_checked_before_call_and_no_icmp_required():
    calls=[]
    class Fixed:
        def observe(self,request,*,timeout):
            calls.append((request.interface_index,request.address,timeout))
            return replace(request,online=True)
    result=collect_fixed(POLICY,((9,"2001:db8::8"),(8,"192.0.2.8"),(7,"203.0.113.8")),
                         Fixed(),now=100)
    assert result.status=="PARTIAL" and len(calls)==1
    assert result.observations[0].source=="FIXED_HELPER" and result.observations[0].online


def test_wrong_fixed_reply_is_not_rebound_to_requested_target():
    class Fixed:
        def observe(self,request,*,timeout):return replace(request,address="192.0.2.9",online=True)
    assert not collect_fixed(POLICY,((7,"192.0.2.8"),),Fixed(),now=100).observations


@pytest.mark.parametrize("script",[
    "import sys;sys.stderr.write('SYNTHETIC_PRIVATE_CANARY');sys.exit(7)",
    "import sys;sys.stdout.buffer.write(b'X'*140000);sys.stdout.flush()",
    "import time;time.sleep(10)",
])
def test_actual_bounded_process_failure_is_closed_and_child_stopped(script,capsys):
    started=time.monotonic()
    with pytest.raises(DiscoveryError,match="^DISCOVERY_UNAVAILABLE$"):
        BoundedRead().run((sys.executable,"-c",script),timeout=.5)
    assert time.monotonic()-started<3
    assert capsys.readouterr()==("","")


def test_actual_fixed_read_process_success():
    assert BoundedRead().run((sys.executable,"-c","print('[]')")) .strip()==b"[]"
