
class ShopObject(TableObject):
    flag = 's'
    flag_description = 'shops'
    custom_random_enable = True
    UNUSED_SHOPS = {0x1a, 0x27}

    def __repr__(self):
        s = 'SHOP %x (%s)\n' % (self.index, self.zone_name)
        s += '{0:0>2X} {1:0>2X} {2:0>2X}\n'.format(
            ord(self.unknown0), self.shop_type, ord(self.unknown2))
        for menu in ['coin', 'item', 'weapon', 'armor']:
            if self.get_bit(menu):
                s += '%s\n' % menu.upper()
                for value in self.wares[menu]:
                    i = ItemObject.get(value)
                    s += '{0:12} {1}\n'.format(i.name, i.price)
        if self.get_bit('spell'):
            s += 'SPELL\n'
            for value in self.spells:
                s += '%s\n' % SpellObject.get(value).name
        return s.strip()

    @property
    def wares_flat(self):
        flat = []
        for menu in ['item', 'weapon', 'armor']:
            flat.extend(self.wares[menu])
        return [ItemObject.get(v) for v in flat]

    @cached_property
    def zone_indexes(self):
        findstr = '. 18({0:0>2X})'.format(self.index)
        zone_indexes = set()
        for meo in MapEventObject.every:
            if findstr in meo.old_pretty:
                zone_indexes.add(meo.zone_index)
        return zone_indexes

    @property
    def zone_name(self):
        if not self.zone_indexes:
            return 'NONE'
        if len(self.zone_indexes) > 1:
            return 'VARIOUS'
        return MapEventObject.zone_names[list(self.zone_indexes)[0]]

    @classproperty
    def after_order(self):
        if 'i' in get_flags():
            return [ItemObject]
        else:
            ItemObject.ranked
        return []

    @classproperty
    def shop_items(self):
        items = set([])
        for s in ShopObject.every:
            for i in s.wares_flat:
                items.add(i)
        return sorted(items, key=lambda i: i.index)

    @classproperty
    def shop_spells(self):
        spells = set([])
        for s in ShopObject.every:
            spells |= set(s.spells)
        spells = [SpellObject.get(s) for s in spells]
        return sorted(spells, key=lambda s: s.index)

    @classproperty
    def shoppable_items(self):
        if hasattr(ShopObject, '_shoppable_items'):
            return ShopObject._shoppable_items

        assert hasattr(ItemObject.get(1), '_rank')
        shoppable_items = list(ShopObject.shop_items)
        for i in ItemObject.every:
            if (i not in shoppable_items and not i.get_bit('unsellable')
                    and i.rank == i.old_data['price'] and i.price > 0
                    and not i.is_coin_set):
                shoppable_items.append(i)
        shoppable_items = sorted(shoppable_items, key=lambda i: i.index)
        ShopObject._shoppable_items = shoppable_items
        return ShopObject.shoppable_items

    @classproperty
    def vanilla_buyable_items(self):
        return [ItemObject.get(i)
                for i in sorted(ShopObject.vanilla_buyable_indexes)]

    @property
    def data_pointer(self):
        return ShopObject.specs.pointer + self.reference_pointer

    def become_coin_shop(self):
        self.unknown0 = b'\x00'
        self.unknown2 = b'\x00'
        self.shop_type = 6

    def read_data(self, filename=None, pointer=None):
        super(ShopObject, self).read_data(filename, pointer)

        if 'shop_type' not in ShopObject.specs.bitnames:
            ShopObject.specs.bitnames['shop_type'] = [
                'pawn', 'coin', 'item', 'weapon', 'armor',
                'spell', 'unk16', 'sell']
        filename = filename or self.filename

        if not hasattr(ShopObject, 'vanilla_buyable_indexes'):
            ShopObject.vanilla_buyable_indexes = set([])

        f = get_open_file(filename)
        f.seek(self.data_pointer)
        self.unknown0 = f.read(1)
        self.shop_type = ord(f.read(1))
        self.unknown2 = f.read(1)
        self.wares = {}
        for menu in ['coin', 'item', 'weapon', 'armor']:
            self.wares[menu] = []
            if self.get_bit(menu):
                assert not self.get_bit('pawn')
                assert not self.get_bit('spell')
                while True:
                    value = int.from_bytes(f.read(2), byteorder='little')
                    if value == 0:
                        break
                    self.wares[menu].append(value)
                    ShopObject.vanilla_buyable_indexes.add(value)

        self.spells = []
        if self.get_bit('spell'):
            assert self.shop_type == 0x20
            while True:
                value = ord(f.read(1))
                if value == 0xFF:
                    break
                self.spells.append(value)

    def write_data(self, filename=None, pointer=None):
        super(ShopObject, self).write_data(filename, pointer)
        filename = filename or self.filename

        f = get_open_file(filename)
        f.seek(self.data_pointer)
        f.write(self.unknown0)
        f.write(bytes([self.shop_type]))
        f.write(self.unknown2)
        for menu in ['coin', 'item', 'weapon', 'armor']:
            if self.get_bit(menu):
                assert self.wares[menu]
                assert not self.get_bit('pawn')
                assert not self.get_bit('spell')
                for value in self.wares[menu]:
                    f.write(value.to_bytes(length=2, byteorder='little'))
                f.write((0).to_bytes(length=2, byteorder='little'))

        if self.get_bit('spell'):
            assert self.shop_type == 0x20
            assert self.spells
            for value in self.spells:
                f.write(bytes([value]))
            f.write(b'\xff')

    @classmethod
    def full_randomize(cls):
        for cls2 in cls.after_order:
            if not (hasattr(cls2, 'randomized') and cls2.randomized):
                raise Exception('Randomize order violated: %s %s'
                                % (cls, cls2))

        ShopObject.class_reseed('full')
        shoppable_items = sorted(ShopObject.shoppable_items,
                                 key=lambda i: i.rank)
        coin_items = set([])
        for s in ShopObject.every:
            if s.wares['coin']:
                coin_items |= set(s.wares_flat)
        shuffled_items = shuffle_normal(
            shoppable_items, random_degree=ShopObject.random_degree)
        new_coin_items = set([])
        for a, b in zip(shoppable_items, shuffled_items):
            if a in coin_items:
                new_coin_items.add(b)
        for i in (coin_items - new_coin_items):
            i.price = min(i.price * 2000, 65000)
        for i in sorted(new_coin_items - coin_items, key=lambda i2: i2.index):
            # Dragonblade - 2500 -> 500000 coins
            if i in ShopObject.vanilla_buyable_items:
                i.price = max(i.price / 2000, 1)
            else:
                i.reseed(salt='coin')
                max_index = len(ItemObject.ranked)-1
                if i.rank < 0:
                    index = max_index
                else:
                    index = ItemObject.ranked.index(i)
                score = index / float(max_index)
                score = mutate_normal(score, 0, 1.0, wide=True,
                                      return_float=True,
                                      random_degree=ItemObject.random_degree)
                score = score ** (8 - (7*(ItemObject.random_degree ** 2)))
                assert 0 <= score <= 1
                price = int(round(score * 2500))
                price = min(2500, max(1, price))
                i.price = price
            i._is_new_coin_item = True

        non_coin_items = set(shoppable_items) - new_coin_items
        assert len(coin_items) == len(new_coin_items)

        for s in ShopObject.every:
            s.reseed(salt='mut')
            while True:
                badflag = False
                if s.wares_flat:
                    if s.wares['coin']:
                        candidates = new_coin_items
                    else:
                        candidates = non_coin_items
                    if ((s.wares['weapon'] or s.wares['armor'])
                            and not s.wares['coin']):
                        if not s.wares['weapon']:
                            candidates = [c for c in candidates
                                          if not c.get_bit('weapon')
                                          or not c.get_bit('equipable')]
                        if not s.wares['armor']:
                            candidates = [c for c in candidates
                                          if c.get_bit('weapon')
                                          or not c.get_bit('equipable')]
                        if not s.wares['item']:
                            candidates = [c for c in candidates
                                          if c.get_bit('equipable')]

                    new_wares = ItemObject.get_similar_set(
                        s.wares_flat, candidates)
                    d = {}
                    d['weapon'] = [i for i in new_wares if i.get_bit('weapon')]
                    d['armor'] = [i for i in new_wares
                                  if i.get_bit('equipable')
                                  and i not in d['weapon']]
                    d['item'] = [i for i in new_wares
                                 if i not in d['weapon'] + d['armor']]

                    if ((s.wares['weapon'] or s.wares['armor'])
                            and not s.wares['coin']):
                        for key in ['weapon', 'armor', 'item']:
                            a = len(s.wares[key])
                            b = len(d[key])
                            if bool(a) != bool(b):
                                badflag = True
                                break
                    else:
                        d['item'].extend(d['weapon'])
                        d['item'].extend(d['armor'])
                        d['weapon'] = []
                        d['armor'] = []

                    if badflag:
                        continue
                    for key in ['weapon', 'armor', 'item']:
                        if s.wares[key]:
                            s.wares[key] = sorted([i.index for i in d[key]])
                break

        spells = list(ShopObject.shop_spells)
        temp_spells = set([])
        shops = list(ShopObject.every)
        random.shuffle(shops)
        for p in shops:
            if not p.spells:
                continue
            if len(temp_spells) < len(p.spells):
                temp_spells = sorted(spells)
            old_spells = [SpellObject.get(s) for s in p.spells]
            new_spells = SpellObject.get_similar_set(old_spells, temp_spells)
            for n in new_spells:
                temp_spells.remove(n)
            p.spells = sorted([s.index for s in new_spells])

        for i in ShopObject.shop_items:
            if i.alt_cursed:
                i.price = max(i.price, i.alt_cursed.price)

class ItemNameObject(TableObject): pass

class SpriteMetaObject(TableObject):
    @property
    def height(self):
        return self.height_misc & 0x1f

    @property
    def memory_load(self):
        return self.height * self.width

class ItemObject(AdditionalPropertiesMixin, PriceMixin, TableObject):
    flag = 'i'
    flag_description = 'items and equipment'
    custom_random_enable = 'i'

    additional_bitnames = ['misc1', 'misc2']
    mutate_attributes = {
        'price': (1, 65500),
    }

    @property
    def name(self):
        return ItemNameObject.get(self.index).name_text.decode('utf8').strip()

    @property
    def is_coin_set(self):
        return 0x18a <= self.index <= 0x18d

    @property
    def is_coin_item(self):
        for s in ShopObject.every:
            if s.wares['coin'] and self.index in s.wares['item']:
                return True
        return False

    @property
    def is_new_coin_item(self):
        if hasattr(self, '_is_new_coin_item'):
            return self._is_new_coin_item
        self._is_new_coin_item = False
        return self.is_new_coin_item

    @property
    def is_buyable(self):
        return not self.is_unbuyable

    @property
    def is_unbuyable(self):
        for s in ShopObject.every:
            for key in s.wares:
                if self.index in s.wares[key]:
                    return False
        return True

    @property
    def is_blue_chest_item(self):
        return self in [b.item for b in BlueChestObject.every]

    @property
    def ip_shuffle_valid(self):
        if 'ip_effect' not in self.additional_properties:
            return False
        if self.index in [0x100, 0x105, 0x10a, 0x10e, 0x13f, 0x142]:
            return False
        return True

    @property
    def ip_shuffle_special(self):
        if not hasattr(self, 'extra'):
            self.read_extra()
        return self.extra[4:6] == '\x0c\x81'

    @property
    def alt_cursed(self):
        if self.get_bit('cursed'):
            return ItemObject.get(self.index+1)
        elif self.index == 0:
            return None
        else:
            test = ItemObject.get(self.index-1)
            if test.get_bit('cursed'):
                return test
        return None

    @property
    def rank(self):
        if hasattr(self, '_rank'):
            return self._rank

        price = self.old_data['price']

        rankdict = {
            0x00: -1,

            0x11: 20000,
            0x12: 20000,
            0x13: 20000,
            0x14: 20000,
            0x15: 20000,
            0x16: 20000,

            0x23: 1000,
            0x2c: 2000,
            0x2d: -1,

            0x2e: 20000,
            0x2f: 20000,
            0x30: 20000,
            0x31: 20000,
            0x32: 20000,
            0x33: 20000,
            0x34: 20000,
            0x35: 20000,

            0x1a6: 100 * 2000,

            0x1ce: 0,
            0x1cf: 0,
            0x1d0: -1,
            0x1d1: 0,
            0x1d2: 0,
        }
        artemis_mods = ['L2_FRUE', 'L2_SPEKKIO', 'L2_KUREJI', 'L2_KUREJI_NB',
                        'L2_KUREJI_HC', 'L2_KUREJI_HC_NB',
                        'LUFIA2_FRUE_V6', 'LUFIA2_SPEKKIO_V6',
                        'LUFIA2_KUREJI_V6',
                        ]
        if get_global_label() in artemis_mods and self.index >= 0x1a7:
            self._rank = -1
        elif self.index in rankdict:
            self._rank = rankdict[self.index]
        elif 0x18e <= self.index <= 0x19b:
            self._rank = price * 2000
        elif price <= 2 or self.get_bit('unsellable'):
            self._rank = -1
        elif self.alt_cursed:
            self._rank = max(price, self.alt_cursed.price)
        else:
            self._rank = price
        self._rank = min(self._rank, 65000)
        return self.rank

    def set_name(self, name_text):
        while len(name_text) < 12:
            name_text += ' '
        assert len(name_text) == 12
        ItemNameObject.get(self.index).name_text = name_text.encode('ascii')

    def cleanup(self):
        if self.index == 0x36 and 'KUREJI' in get_global_label().upper():
            for charname in ['maxim', 'selan', 'guy', 'artea',
                             'tia', 'dekar', 'lexis']:
                self.set_bit(charname, True)

        if self.is_new_coin_item and not self.is_coin_item:
            self.price = max(self.price, self.old_data['price'])
        if self.is_blue_chest_item or self.is_coin_item:
            self.set_bit('ban_ancient_cave', True)
        self.price = int(round(self.price))
        if self.is_coin_item:
            self.price = min(self.price, 2500)
            return
        if 's' not in get_flags() and 'i' not in get_flags():
            return
        self.price_clean()

    @staticmethod
    def intershuffle():
        ItemObject.class_reseed('ip')
        candidates = [i for i in ItemObject.ranked if i.ip_shuffle_valid]
        negranks = [c for c in candidates if c.rank < 0]
        for c in negranks:
            candidates.remove(c)
            assert c not in candidates
            max_index = len(candidates)
            index = random.randint(random.randint(random.randint(
                0, max_index), max_index), max_index)
            candidates.insert(index, c)

        cand2s = [c for c in candidates if c.ip_shuffle_special]
        cand1s = [c for c in candidates if c not in cand2s]
        for candidates in [cand1s, cand2s]:
            shuffled = shuffle_normal(
                candidates, wide=True, random_degree=ItemObject.random_degree)

            if candidates is cand2s:
                extras = [i.extra for i in shuffled]
                for i, extra in zip(candidates, extras):
                    startlen = len(i.extra)
                    i.extra = i.extra[:4] + extra[4:11] + i.extra[11:]
                    assert len(i.extra) == startlen

            shuffled = [i.additional_properties['ip_effect'] for i in shuffled]
            for i, ip in zip(candidates, shuffled):
                i.additional_properties['ip_effect'] = ip

        ItemObject.class_reseed('equip')
        equip_types = ['weapon', 'armor', 'shield',
                       'helmet', 'ring', 'jewel']
        for equip_type in equip_types:
            equips = [i for i in ItemObject.every
                      if i.get_bit('equipable') and i.get_bit(equip_type)]
            ordering = list(range(7))
            random.shuffle(ordering)
            for i in equips:
                old_equip = i.equipability
                assert not (old_equip & 0x80)
                new_equip = 0
                for n, m in enumerate(ordering):
                    if bool(old_equip & (1 << m)):
                        new_equip |= (1 << n)
                if random.random() < (ItemObject.random_degree ** 3):
                    new_equip = new_equip | (random.randint(0, 0x7f) &
                                             random.randint(0, 0x7f))
                if random.random() < (ItemObject.random_degree ** 1.5):
                    temp = new_equip & (random.randint(0, 0x7f) |
                                        random.randint(0, 0x7f))
                    if temp:
                        new_equip = temp
                assert new_equip
                i.equipability = new_equip

        equips = [i for i in ItemObject.every
                  if i.get_bit('equipable') and i.item_type & 0x3F]
        if 'everywhere' in get_activated_codes():
            # doesn't work, the game checks for multiple bits at equip menu
            print('EQUIP EVERYWHERE CODE ACTIVATED')
            for i in equips:
                equip_score = 6 - (bin(i.equipability).count('1') - 1)
                num_slots = 1 + ((equip_score / 6.0) * 5)
                assert equip_score >= 0
                num_slots = mutate_normal(
                    num_slots, minimum=1, maximum=6,
                    random_degree=ItemObject.random_degree ** 0.5, wide=True)
                bits = random.sample(range(6), num_slots)
                new_item_type = 0
                for b in bits:
                    new_item_type |= (1 << b)
                old_item_type = i.item_type
                i.item_type = 0
                for b in range(6):
                    if random.random() < ItemObject.random_degree:
                        i.item_type |= (new_item_type & (1 << b))
                    else:
                        i.item_type |= (old_item_type & (1 << b))
                assert not old_item_type & 0xC0

        elif 'anywhere' in get_activated_codes():
            # works, but 'strongest' looks for appropriate icon
            print('EQUIP ANYWHERE CODE ACTIVATED')
            for i in equips:
                if random.random() < (ItemObject.random_degree ** 1.5):
                    equip_type = random.choice(equip_types)
                    i.item_type = 0
                    i.set_bit(equip_type, True)

    @classmethod
    def mutate_all(cls):
        super(ItemObject, cls).mutate_all()
        addprops = ['increase_atp', 'increase_dfp', 'increase_str',
                    'increase_agl', 'increase_int', 'increase_gut',
                    'increase_mgr']
        minmaxes = {}
        for ap in addprops:
            candidates = [i for i in ItemObject.every
                          if ap in i.additional_properties]
            assert candidates
            values = [c.additional_properties[ap] for c in candidates]
            minmaxes[ap] = (min(values), max(values))

        for i in ItemObject.every:
            i.reseed(salt='mut2')
            for ap in addprops:
                if ap not in i.additional_properties:
                    continue
                lower, upper = minmaxes[ap]
                value = i.additional_properties[ap]
                value = mutate_normal(value, lower, upper,
                                      random_degree=ItemObject.random_degree)
                i.additional_properties[ap] = value

class MonsterObject(TableObject):
    flag = 'm'
    flag_description = 'monsters'
    custom_random_enable = True

    intershuffle_attributes = [
        'hp', 'attack', 'defense', 'agility', 'intelligence',
        'guts', 'magic_resistance', 'xp', 'gold']

    mutate_attributes = {
        'level': None,
        'hp': None,
        'attack': None,
        'defense': None,
        'agility': None,
        'intelligence': None,
        'guts': None,
        'magic_resistance': None,
        'xp': None,
        'gold': None,
    }

    OVERWORLD_SPRITE_TABLE_FILENAME = path.join(
        tblpath, 'monster_overworld_sprites.txt')
    monster_overworld_sprites = {}
    for line in read_lines_nocomment(OVERWORLD_SPRITE_TABLE_FILENAME):
        monster_index, sprite_index, name = line.split(' ', 2)
        monster_index = int(monster_index, 0x10)
        sprite_index = int(sprite_index, 0x10)
        monster_overworld_sprites[monster_index] = sprite_index

    @property
    def intershuffle_valid(self):
        return (self.rank >= 0 and not 0xA7 <= self.index <= 0xAA
                and self.index not in [0xdf])

    @cached_property
    def name(self):
        if b'\x00' in self.name_text:
            null_index = self.name_text.index(b'\x00')
            name_text = self.name_text[:null_index]
        else:
            name_text = self.name_text
        name = name_text.decode('utf8').strip()
        return ''.join([c for c in name if c in printable])

    @property
    def has_drop(self):
        return self.misc == 3

    @property
    def drop(self):
        return ItemObject.get(self.drop_index)

    @property
    def drop_index(self):
        return self.drop_data & 0x1FF

    @property
    def drop_rate(self):
        return self.drop_data >> 9

    @property
    def is_boss(self):
        return self.index >= 0xBC

    @property
    def sprite_meta(self):
        return SpriteMetaObject.get(self.battle_sprite-1)

    @property
    def width(self):
        return self.sprite_meta.width * 8

    @property
    def height(self):
        return self.sprite_meta.height * 8

    @property
    def rank(self):
        if hasattr(self, '_rank'):
            return self._rank

        RANK_ATTRS = ['level', 'hp', 'hp', 'attack',
                      'intelligence', 'agility', 'xp', 'xp']
        NUM_CHOOSE = 5
        orderings = {}
        for attr in RANK_ATTRS:
            orderings[attr] = sorted(
                MonsterObject.every,
                key=lambda m: (m.old_data[attr],
                               m.old_data['xp'] * m.old_data['hp'],
                               m.signature))

        for m in MonsterObject.every:
            if m.is_boss:
                m.old_rank = m.old_data['level'] * (m.old_data['hp'] ** 2)
            else:
                m.old_rank = (m.old_data['level'] * m.old_data['hp']
                              * m.old_data['xp'])
                assert m.old_rank != 0
            ranks = [orderings[attr].index(m) for attr in RANK_ATTRS]
            while len(ranks) > NUM_CHOOSE:
                ranks.remove(min(ranks))
            assert len(ranks) == NUM_CHOOSE
            m._rank = sum(ranks) / len(ranks)

        old_ranked = sorted(MonsterObject.every, key=lambda m: m.old_rank)
        for m in MonsterObject.every:
            m.old_rank = old_ranked.index(m)

        new_ranked = sorted(MonsterObject.every, key=lambda m: m._rank)
        for m in MonsterObject.every:
            m._rank = new_ranked.index(m)

        return self.rank

    @classmethod
    def intershuffle(cls):
        MonsterObject.class_reseed('inter')
        super(MonsterObject, cls).intershuffle(
            candidates=[m for m in MonsterObject.every if not m.is_boss])
        super(MonsterObject, cls).intershuffle(
            candidates=[m for m in MonsterObject.every if m.is_boss])

    def guess_sprite(self):
        if self.index in self.monster_overworld_sprites:
            return self.monster_overworld_sprites[self.index]
        elif (get_global_label() == 'LUFIA2_SPEKKIO_V6'
                and 'Lady Spider' in self.name):
            return 0x89
        else:
            return 0x94

    def set_drop(self, item):
        if isinstance(item, ItemObject):
            item = item.index
        new_data = self.drop_data & 0xFE00
        self.drop_data = new_data | item

    def set_drop_rate(self, rate):
        new_data = self.drop_data & 0x1FF
        self.drop_data = new_data | (rate << 9)

    def scale_stats(self, scale_amount):
        if 'jelly' in self.name.lower():
            return
        self._scaled = True
        for attr in sorted(self.mutate_attributes):
            value = int(round(getattr(self, attr) * scale_amount))
            setattr(self, attr, value)

    def read_data(self, filename=None, pointer=None):
        super(MonsterObject, self).read_data(filename, pointer)
        filename = filename or self.filename
        if self.has_drop:
            f = get_open_file(filename)
            f.seek(self.pointer+self.specs.total_size)
            self.drop_data = int.from_bytes(f.read(2), byteorder='little')

    def write_data(self, filename=None, pointer=None):
        super(MonsterObject, self).write_data(filename, pointer)
        filename = filename or self.filename
        if self.has_drop:
            f = get_open_file(filename)
            f.seek(self.pointer+self.specs.total_size)
            f.write(self.drop_data.to_bytes(length=2, byteorder='little'))

    def mutate(self):
        super(MonsterObject, self).mutate()
        if self.has_drop:
            i = self.drop.get_similar()
            self.set_drop(i)

    def cleanup(self):
        for (attr, bytesize, _) in self.specs.attributes:
            if attr in self.mutate_attributes:
                value = getattr(self, attr)
                if attr in ['gold', 'xp']:
                    value = value / get_difficulty()
                else:
                    value = value * get_difficulty()
                value = int(round(value))

                minimum = 0
                maximum = (1<<(bytesize*8))-1
                if not minimum <= value <= maximum:
                    value = min(maximum, max(minimum, value))
                setattr(self, attr, value)

        if self.is_boss and not hasattr(self, '_scaled'):
            for attr in self.mutate_attributes:
                if getattr(self, attr) < self.old_data[attr]:
                    setattr(self, attr, self.old_data[attr])

        if 'easymodo' in get_activated_codes():
            for attr in ['hp', 'attack', 'defense', 'agility', 'intelligence',
                         'guts', 'magic_resistance']:
                setattr(self, attr, 1)

class FormationObject(TableObject):
    custom_random_enable = 'f'

    UNUSED_FORMATIONS = [0xA5]

    def __repr__(self):
        ss = []
        for i, m in enumerate(self.monsters):
            if m is not None:
                ss.append('#{0} {1:0>2X}-{2}'.format(i+1, m.index, m.name))
        ss = ', '.join(ss)
        return 'FORMATION {0:0>2X}: {1}'.format(self.index, ss)

    @cached_property
    def monsters(self):
        return [MonsterObject.get(index) if index < 0xFF else None
                for index in self.monster_indexes]

    @cached_property
    def clean_monsters(self):
        return [m for m in self.monsters if m is not None]

    @property
    def rank(self):
        if self.monsters[0] is None:
            return -1
        return self.monsters[0].rank

    def guess_sprite(self):
        if self.monsters[0] is None:
            return None
        return self.monsters[0].guess_sprite()

    def preprocess(self):
        self.monsters

class MapFormationsObject(TableObject):
    def __repr__(self):
        s = '\n'.join(['{0:0>2X}: {1}'.format(i, f)
                       for (i, f) in enumerate(self.formations)])
        return 'MAP FORMATIONS {0:0>2X}\n{1}'.format(self.index, s)

    @classproperty
    def base_pointer(self):
        assert self.specs.pointer == 0xbb9ac
        return self.specs.pointer

    @classproperty
    def all_pointers(self):
        if hasattr(MapFormationsObject, '_all_pointers'):
            return MapFormationsObject._all_pointers

        all_pointers = {
            mfo.reference_pointer + MapFormationsObject.base_pointer
            for mfo in MapFormationsObject.every}
        MapFormationsObject._all_pointers = sorted(all_pointers)
        return MapFormationsObject.all_pointers

    @property
    def formations_pointer(self):
        return self.base_pointer + self.reference_pointer

    @property
    def num_formations(self):
        index = self.all_pointers.index(self.formations_pointer)
        try:
            next_pointer = self.all_pointers[index+1]
        except IndexError:
            return 0
        return next_pointer - self.formations_pointer

    @property
    def formations(self):
        self.preprocess()
        return [FormationObject.get(i) for i in self.formation_indexes]

    def preprocess(self):
        if hasattr(self, 'formation_indexes'):
            return
        f = get_open_file(get_outfile())
        f.seek(self.formations_pointer)
        self.formation_indexes = list(map(int, f.read(self.num_formations)))

    def write_data(self, filename=None, pointer=None):
        super().write_data(filename, pointer)
        if self.num_formations <= 0:
            return
        f = get_open_file(get_outfile())
        f.seek(self.formations_pointer)
        f.write(bytes(self.formation_indexes))
