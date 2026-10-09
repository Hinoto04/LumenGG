from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from card.models import Character
from battlelog.services import create_standalone_session
from LumenGG.asgi import application
import uuid


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND':'channels.layers.InMemoryChannelLayer'}})
class MobileRealtimeTests(TransactionTestCase):
    def test_mobile_actions_broadcast_to_mobile_and_legacy_viewers(self):
        character=Character.objects.create(name='WS test',description='',group='',datas={'hand':{'5000':5}},img='')
        session=create_standalone_session('a','b',character,character)

        async def scenario():
            controller=WebsocketCommunicator(application,f'/ws/mobile/v1/calculators/{session.view_token}/')
            viewer=WebsocketCommunicator(application,f'/ws/battlelog/session/{session.view_token}/')
            self.assertTrue((await controller.connect())[0]);self.assertTrue((await viewer.connect())[0])
            first=await controller.receive_json_from();self.assertFalse(first['state']['can_control'])
            await viewer.receive_json_from()
            await controller.send_json_to({'type':'authenticate','request_id':'auth','control_token':session.control_token})
            auth=await controller.receive_json_from();self.assertTrue(auth['state']['can_control'])
            body={'action':'hp','target':'p1','amount':-100,'expected_version':auth['state']['version'],'action_id':str(uuid.uuid4())}
            await controller.send_json_to({'type':'action','request_id':'one','payload':body})
            response=None
            for _ in range(4):
                message=await controller.receive_json_from()
                if message.get('request_id')=='one':response=message;break
            self.assertTrue(response['ok']);self.assertEqual(response['state']['players']['p1']['hp'],4900)
            legacy=None
            for _ in range(5):
                message=await viewer.receive_json_from()
                if message.get('state',{}).get('players',{}).get('p1',{}).get('hp')==4900:legacy=message;break
            self.assertIsNotNone(legacy)
            self.assertEqual(legacy['state']['control_url'],'')
            await controller.disconnect();await viewer.disconnect()
        async_to_sync(scenario)()
