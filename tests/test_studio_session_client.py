"""Portable bounded contracts; HTTP recovery never reads private modules."""
from uuid import uuid4
import json
import pytest
from pydantic import ValidationError
from test_studio_client import FakeTransport
from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.studio_session import ScientificFigureRequest, StudioConversationSave


def test_authenticated_session_roundtrip_and_png_request():
    identity=uuid4().hex
    messages=[{'role':'user','content':'A scientific request'}]
    response={'conversation_id':identity,'revision':1,'messages':messages,
        'updated_at':'2026-10-10T12:00:00+00:00','expires_at':'2026-10-10T15:00:00+00:00'}
    transport=FakeTransport([(200,response),(200,{'conversations':[response]}),(200,response),(200,b'PNG')])
    client=GeoWorldBackendClient('https://example.test',token='token-1',transport=transport)
    saved=client.save_studio_conversation(identity,StudioConversationSave(messages=messages))
    assert saved.revision==1
    assert client.recent_studio_conversations()[0]==saved
    assert client.restore_studio_conversation(identity)==saved
    assert client.scientific_figure('b'*32,ScientificFigureRequest(fields=('porosity','delta_vp')))==b'PNG'
    assert [c[0] for c in transport.calls]==['PUT','GET','GET','POST']
    assert all(c[2]['Authorization']=='Bearer token-1' for c in transport.calls)
    assert json.loads(transport.calls[-1][3])=={'fields':['porosity','delta_vp'],'display_scale':1.,'dpi':200}


@pytest.mark.parametrize('fields',[[],['porosity']*2,['porosity']*5,['a'*81]])
def test_optional_figure_request_is_bounded(fields):
    with pytest.raises(ValidationError):
        ScientificFigureRequest(fields=fields)


def test_server_revision_conflict_is_actionable():
    client=GeoWorldBackendClient('https://example.test',token='token-1',transport=FakeTransport([
        (409,{'detail':'Conversation changed in another session. Restore recent work.'})]))
    with pytest.raises(GeoWorldClientError,match='Restore recent work'):
        client.save_studio_conversation(uuid4().hex,StudioConversationSave())
