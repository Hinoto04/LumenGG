from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MobileMigrationTests(TransactionTestCase):
    def test_existing_decks_get_unique_ids_and_duplicate_quantities_are_archived(self):
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        before=[('deck','0013_alter_deck_version'),('collection','0010_collectioncard_character_item_type')]
        try:
            executor.migrate(before)
            state_targets=[node for node in latest if node[0] not in {'deck','collection'}]+before
            apps=executor.loader.project_state(state_targets).apps
            User=apps.get_model('auth','User')
            Character=apps.get_model('card','Character')
            Card=apps.get_model('card','Card')
            CollectionCard=apps.get_model('collection','CollectionCard')
            Collected=apps.get_model('collection','Collected')
            Deck=apps.get_model('deck','Deck')
            user=User.objects.create(username='migration-smoke')
            character=Character.objects.create(name='migration',description='',group='',datas={},img='')
            card=Card.objects.create(name='migration',code='MIG-001',character_id=character.pk)
            item=CollectionCard.objects.create(card_id=card.pk,name='migration')
            decks=[Deck.objects.create(name=str(i),author_id=user.pk,character_id=character.pk) for i in range(2)]
            first=Collected.objects.create(user_id=user.pk,card_id=item.pk,amount=4)
            last=Collected.objects.create(user_id=user.pk,card_id=item.pk,amount=9)
            executor=MigrationExecutor(connection);executor.migrate(latest)
            apps=executor.loader.project_state(latest).apps
            NewDeck=apps.get_model('deck','Deck')
            quantities=apps.get_model('collection','Collected')
            archive=apps.get_model('collection','CollectedDuplicateArchive')
            ids=list(NewDeck.objects.filter(pk__in=[d.pk for d in decks]).values_list('mobile_id',flat=True))
            self.assertEqual(len(set(ids)),2)
            self.assertTrue(all(ids))
            self.assertEqual(quantities.objects.get(user_id=user.pk,card_id=item.pk).pk,last.pk)
            self.assertEqual(quantities.objects.get(user_id=user.pk,card_id=item.pk).amount,9)
            self.assertEqual(set(archive.objects.filter(original_id__in=[first.pk,last.pk]).values_list('amount',flat=True)),{4,9})
        finally:
            MigrationExecutor(connection).migrate(latest)
