from django.db import migrations
import re

def classify(apps,schema_editor):
    Post=apps.get_model('posts','Post')
    keywords=[('food',('coffee','café','food','latte','recipe','breakfast','dinner')),('music',('music','song','playlist','concert','album')),('technology',('technology','code','coding','software','computer','robot','tech')),('nature',('forest','trail','trees','hiking','nature','outdoors','scenic')),('design',('design','architecture','creative','art','inspiration','textures','lines')),('travel',('travel','ocean','beach','coast','city','places','route','weekend','horizon','street')),('photography',('photo','camera','frame','light','sunset','colours','colors')),('wellness',('fitness','wellbeing','gym','workout','running','yoga')),('style',('style','fashion','outfit','everyday','ritual','life'))]
    for post in Post.objects.filter(topic='').iterator():
        words=set(re.findall(r'\w+',post.text.lower()))
        topic=next((key for key,terms in keywords if words.intersection(terms)),'')
        if not topic:
            name=str(post.image).lower()
            topic=next((key for term,key in [('coffee','food'),('forest','nature'),('architecture','design'),('city','travel'),('coast','travel'),('beach','travel'),('sunset','photography')] if term in name),'')
        if topic: Post.objects.filter(pk=post.pk).update(topic=topic)

class Migration(migrations.Migration):
    dependencies=[('posts','0002_post_topic')]
    operations=[migrations.RunPython(classify,migrations.RunPython.noop)]
