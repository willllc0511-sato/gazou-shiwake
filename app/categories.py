"""ImageNet の分類名を、ネットショップの商品の仕分け先（日本語）にまとめる。
語が分類名に単語として含まれていれば、その仕分け先にする。どれにも当たらなければ「その他」。"""
from __future__ import annotations

import re

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("靴", ("shoe", "sneaker", "boot", "sandal", "clog", "loafer")),
    ("衣類", ("shirt", "jersey", "sweatshirt", "cardigan", "suit", "jean", "miniskirt", "kimono", "gown", "trench coat",
              "fur coat", "lab coat", "poncho", "abaya", "bikini", "swimming trunks", "brassiere", "pajama", "apron",
              "bow tie", "Windsor tie", "stole", "sock", "mitten", "cowboy hat", "sombrero", "bonnet", "cap")),
    ("かばん・小物", ("backpack", "purse", "wallet", "mailbag", "sunglass", "umbrella", "necklace", "digital watch",
                     "analog clock", "wall clock", "stopwatch")),
    ("電子機器", ("laptop", "notebook", "desktop computer", "monitor", "screen", "keyboard", "mouse", "cellular telephone",
                 "iPod", "remote control", "television", "loudspeaker", "microphone", "projector", "printer",
                 "camera", "modem", "joystick", "hard disc", "headphone", "hand-held computer")),
    ("台所用品", ("cup", "mug", "plate", "bowl", "teapot", "frying pan", "wok", "spatula", "ladle", "pitcher",
                 "water bottle", "beer bottle", "wine bottle", "measuring cup", "coffeepot", "espresso maker",
                 "toaster", "waffle iron", "microwave", "Crock Pot", "Dutch oven", "caldron", "saltshaker",
                 "can opener", "corkscrew", "strainer", "goblet", "beer glass", "cocktail shaker", "refrigerator")),
    ("食品", ("pizza", "banana", "orange", "lemon", "strawberry", "pineapple", "fig", "pomegranate", "jackfruit",
             "custard apple", "Granny Smith", "hotdog", "cheeseburger", "bagel", "pretzel", "French loaf",
             "ice cream", "ice lolly", "trifle", "chocolate sauce", "dough", "meat loaf", "burrito", "potpie",
             "consomme", "hot pot", "guacamole", "carbonara", "espresso", "red wine", "eggnog", "broccoli",
             "cauliflower", "cabbage", "zucchini", "cucumber", "bell pepper", "mushroom", "corn", "acorn squash",
             "butternut squash", "spaghetti squash", "artichoke", "cardoon", "mashed potato")),
    ("家具", ("chair", "table", "desk", "studio couch", "wardrobe", "bookcase", "chiffonier", "cradle", "crib",
             "four-poster", "park bench", "rocking chair", "throne", "china cabinet", "file", "entertainment center",
             "medicine chest", "shoji", "window shade", "quilt", "pillow")),
    ("文房具", ("ballpoint", "fountain pen", "pencil box", "pencil sharpener", "rubber eraser", "binder", "envelope",
               "paper towel", "rule", "carpenter's kit")),
]


# 語の区切りで当てる（"cap" が "capuchin"（猿）に、"corn" が "acorn" に当たらないように）
_PATTERNS = [(name, re.compile(r"\b(" + "|".join(re.escape(w.lower()) for w in words) + r")s?\b")) for name, words in RULES]


def category_of(label: str) -> str:
    low = label.lower()
    for name, pat in _PATTERNS:
        if pat.search(low):
            return name
    return "その他"
