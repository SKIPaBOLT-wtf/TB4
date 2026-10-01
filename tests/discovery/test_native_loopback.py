"""Actual OS query, opted in only by a documented isolated CI qualification."""
import json
import os
import socket
import sys

import pytest

from tb4.discovery_catalogue import Interface, Scope
from tb4.discovery_native import BoundedRead, NativeNeighbors, collect_neighbors, system_program

pytestmark=pytest.mark.skipif(os.environ.get("TB4_REQUIRE_NATIVE_DISCOVERY")!="1",
                             reason="Native loopback query requires isolated qualification opt-in")


def loopback():
    if sys.platform=="linux":
        return Interface("lo",socket.if_nametoindex("lo"),("127.0.0.0/8","::1/128"),"ISOLATED")
    if sys.platform=="win32":
        import base64
        script=("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
                "$ErrorActionPreference='Stop';$r=@(Get-NetIPAddress -IPAddress '127.0.0.1' "
                "-AddressFamily IPv4 | Select-Object InterfaceIndex,InterfaceAlias);"
                "ConvertTo-Json -InputObject $r -Compress -Depth 3")
        raw=BoundedRead().run((system_program("win32"),"-NoProfile","-NonInteractive",
            "-EncodedCommand",base64.b64encode(script.encode("utf-16-le")).decode()),timeout=10)
        rows=json.loads(raw.decode("utf-8-sig"))
        assert len(rows)==1
        return Interface(rows[0]["InterfaceAlias"],rows[0]["InterfaceIndex"],("127.0.0.0/8","::1/128"),"ISOLATED")
    pytest.fail("Required native platform unavailable")


def test_actual_loopback_identity_and_cache_read_only(capsys):
    interface=loopback()
    result=collect_neighbors(Scope((interface,)),NativeNeighbors(),clock=lambda:100)
    assert result.status=="COMPLETE"
    assert result.completed_queries==1 and result.failed_queries==0
    assert all(o.interface_index==interface.index and not o.online for o in result.observations)
    assert capsys.readouterr()==("","")


def test_actual_mismatched_loopback_identity_refuses_before_neighbor_read():
    from dataclasses import replace
    interface=replace(loopback(),name="synthetic-wrong-interface")
    result=collect_neighbors(Scope((interface,)),NativeNeighbors(),clock=lambda:100)
    assert result.status=="UNAVAILABLE" and not result.observations
