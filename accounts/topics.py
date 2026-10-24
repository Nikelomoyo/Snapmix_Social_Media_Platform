"""The same topic vocabulary is used by onboarding, post forms and ranking."""
TOPICS = [
    ('travel','Travel & places','coast','↗'),
    ('nature','Nature & outdoors','forest','❋'),
    ('food','Food & coffee','coffee','☕'),
    ('photography','Photography','sunset','◉'),
    ('design','Art & design','architecture','◇'),
    ('technology','Technology','city','⌘'),
    ('music','Music & culture','city','♫'),
    ('wellness','Fitness & wellbeing','beach','☀'),
    ('style','Style & everyday life','coastline','✦'),
]
TOPIC_CHOICES = [(key,label) for key,label,_,_ in TOPICS]
TOPIC_NAMES = dict(TOPIC_CHOICES)
KEYWORDS = {
    'food':('coffee','café','cafe','food','cooking','latte','recipe','breakfast','dinner','lunch'),
    'music':('music','song','playlist','concert','album','listening','headphones'),
    'technology':('technology','code','coding','software','computer','app','robot','tech'),
    'nature':('forest','trail','trees','hiking','nature','outdoors','green','scenic'),
    'design':('design','architecture','creative','art','inspiration','mood board','textures','lines'),
    'travel':('travel','ocean','beach','coast','city','places','route','weekend','horizon','street'),
    'photography':('photo','photography','camera','frame','light','sunset','colours','colors'),
    'wellness':('fitness','wellbeing','wellness','gym','workout','running','yoga','slow down'),
    'style':('style','fashion','outfit','everyday','ritual','life'),
}

def infer_topic(text):
    import re
    words=set(re.findall(r"[\w]+",text.lower()))
    for topic,phrases in KEYWORDS.items():
        if any(phrase in text.lower() if ' ' in phrase else phrase in words for phrase in phrases):
            return topic
    return ''
