import copy
import pytest
from tools.development.ledger import LedgerError, validate_journal
from test_ledger import event, SHA


def rows():
    intent=event()
    result=event(2,'OUTCOME',intent['event_id'],'RECORDED')
    result['evidence']=['src/tb4/synthetic.py','docs/synthetic.md','tests/test_synthetic.py']
    correction=event(3,'CORRECTION',result['event_id'],'RECORDED')
    correction.update(observed=result['observed'],evidence=['docs/source-receipt.md'],
        source_evidence_correction=dict(old_value=list(result['evidence']),new_value=['docs/source-receipt.md']))
    return [intent,result,correction]


def test_source_receipt_correction_keeps_original_bytes_result_and_pending_semantics():
    events=rows();before=copy.deepcopy(events)
    found,pending=validate_journal(events,'RP-001','A001',lambda s:s==SHA)
    assert not pending and found[events[1]['event_id']]==before[1] and events==before
    with pytest.raises(LedgerError):
        validate_journal(events[:-1],'RP-001','A001',lambda s:s==SHA)


@pytest.mark.parametrize('case',['source','action','observation','old-list','empty-receipt',
    'receipt-mismatch','unsafe-receipt','pass-target','started-target','duplicate','mixed'])
def test_source_receipt_correction_rejects_forged_or_ambiguous_history(case):
    events=rows();target=events[1];row=events[-1];patch=row['source_evidence_correction']
    if case=='source':row['source_ref']='b'*40
    elif case=='action':row['action_id']='OTHER'
    elif case=='observation':row['observed']='Invented result'
    elif case=='old-list':patch['old_value'].pop()
    elif case=='empty-receipt':patch['new_value']=[];row['evidence']=[]
    elif case=='receipt-mismatch':row['evidence']=['docs/different.md']
    elif case=='unsafe-receipt':patch['new_value']=['src/not-a-receipt.py'];row['evidence']=patch['new_value']
    elif case=='pass-target':target['outcome']='PASS'
    elif case=='started-target':target['event']='STARTED'
    elif case=='mixed':row['reference_correction']=dict(field='related_event',old_value=None,new_value=events[0]['event_id'])
    elif case=='duplicate':
        duplicate=copy.deepcopy(row);duplicate.update(event_id='RP-001-A001-0004',sequence=4)
        events.append(duplicate)
    with pytest.raises(LedgerError):validate_journal(events,'RP-001','A001',lambda s:True)
