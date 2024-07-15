from typing import List, Tuple
from tqdm import tqdm, trange
import os, csv, random  # noqa: E401

# from numpy import argmax
import argparse


"""
Assume 3 players, including hero

Rules:
* Each player is delt 3 cards each
* Score is sum of cards with same suit (face are 10s, ace is 11)
* Action can be to draw from deck or discard pile, or go down (giving each player 1 more turn)

At turn N, what is the hero's threshold to win if they go down?

Greedy startegy:
* If the sum of the cards in the hand is greater than the threshold, go down; otherwise...
* Draw from discard if card would raise our score to above the threshold
* Else, draw from deck

* Drop lowest value card always
"""

parser = argparse.ArgumentParser(description="Simulate 31, the card game")

parser.add_argument("--player_cnt", type=int, default=3, help="Number of players")
parser.add_argument("--hero_id", type=int, default=0, help="Hero ID")  # todo randomize
parser.add_argument("--threshold", type=int, default=22, help="Threshold value")
parser.add_argument("--samples", type=int, default=int(1e2), help="Number of samples")

args = parser.parse_args()

PLAYER_CNT = args.player_cnt
HERO_ID = args.hero_id
THRESHOLD = args.threshold
SAMPLES = args.samples

assert 1 < PLAYER_CNT
assert 0 <= HERO_ID < PLAYER_CNT
assert 0 < THRESHOLD < 31
assert 0 < SAMPLES


def all_but_idx(lst: list, idx: int) -> list:
    return lst[:idx] + lst[idx + 1 :]


def argmax(lst: list):
    return max(range(len(lst)), key=lambda i: lst[i])


class Card:
    def __init__(self, value, suit):
        assert 0 <= suit < 4
        assert 2 <= value <= 11
        self.val: int = value
        self.suit: int = suit

    def as_tuple(self) -> tuple[int, int]:
        return (self.val, self.suit)

    def __repr__(self):
        # return f"({self.val}, {self.suit})"
        return str(self.as_tuple())


class Deck:
    def __init__(self):
        self.cards = []
        for suit in range(4):
            for val in range(2, 10):
                self.cards.append(Card(val, suit))
            for _ in range(4):
                self.cards.append(Card(10, suit))
            self.cards.append(Card(11, suit))

        self.shuffle()

        self.pile = []  # discard pile
        self.discard: Card = self.cards.pop()  # top of discard pile

    def __repr__(self):
        return str(sorted(self.cards, key=lambda c: (c.suit, c.val)))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self) -> Card:
        if self.size() == 0:
            self.cards = self.pile
            self.pile = []
            self.shuffle()
            assert self.size() == 52 - 3 * PLAYER_CNT - 1
        return self.cards.pop()

    def size(self) -> int:
        return len(self.cards)


class Player:
    cnt = 0

    def __init__(self, deck: Deck):
        self.id = Player.cnt
        Player.cnt += 1

        self.deck: Deck = deck
        self.hand: list[Card] = [deck.draw() for _ in range(3)]

        self.down = False

    def hand_value(self, hand: list[Card] = None) -> int:
        c1, c2, c3 = hand or self.hand

        if c1.suit == c2.suit == c3.suit:
            return c1.val + c2.val + c3.val
        elif c1.suit == c2.suit:
            return max(c1.val + c2.val, c3.val)
        elif c1.suit == c3.suit:
            return max(c1.val + c3.val, c2.val)
        elif c2.suit == c3.suit:
            return max(c2.val + c3.val, c1.val)
        return max(c1.val, c2.val, c3.val)

    def hand_value_suited(self, hand: list[Card] = None) -> Tuple[int, int]:
        c1, c2, c3 = hand or self.hand

        if c1.suit == c2.suit:
            return (
                (c1.val + c2.val + c3.val, c1.suit)
                if (c1.suit == c3.suit)
                else (
                    (c12v, c1.suit)
                    if (c12v := c1.val + c2.val) > c3.val
                    else (c3.val, c3.suit)
                )
            )
        elif c1.suit == c3.suit:
            return (
                (c13v, c1.suit)
                if (c13v := c1.val + c3.val) > c2.val
                else (c2.val, c2.suit)
            )
        elif c2.suit == c3.suit:
            return (
                (c23v, c2.suit)
                if (c23v := c2.val + c3.val) > c1.val
                else (c1.val, c1.suit)
            )
        else:
            return max(self.hand, key=lambda c: c.val).as_tuple()

    def best_value_given_card(self, card: Card = None) -> Tuple[int, list[Card], Card]:
        card = card or self.deck.discard
        val, hand, disc = self.hand_value(), self.hand, card

        for i in range(len(self.hand)):
            test_hand = [card] + all_but_idx(self.hand, i)
            test_val = self.hand_value(test_hand)
            test_disc = self.hand[i]
            if test_val > val or (test_val == val and test_disc.val < disc.val):
                val, hand = test_val, test_hand
                disc = test_disc

        return val, hand, disc

    @property
    def is_over(self) -> bool:
        return self.down or self.hand_value() == 31

    def turn(self):
        assert not self.is_over  # (we are so back)
        hv, hs = self.hand_value_suited()
        is_hero = self.id == HERO_ID

        if is_hero:
            if hv >= THRESHOLD:
                self.down = True
                return

        SWAP_DELTA = 3  # how much better must discard improve our hand to take it
        # optimal value/hand considering discard
        d_val, d_hand, d_disc = self.best_value_given_card(self.deck.discard)
        if d_val > hv:
            # ! this is maybe bad? i.e. we could drop a 10 and take a 2 if it's suited w a 9
            # we should def take if it surpasses our threhold
            if (is_hero and d_val > THRESHOLD) or (d_val - SWAP_DELTA > hv):
                # print("take discard")
                self.hand, self.deck.discard = d_hand, d_disc
                return

        # !!! SOFT LOCK HERE !!! we may have value >12 but same suit as another player; never swap suits when committed. this should be okay for aggro hero but not for regulars (?)
        new_card = self.deck.draw()

        self.deck.pile.append(self.deck.discard)
        self.deck.discard = None

        n_val, n_hand, n_disc = self.best_value_given_card(new_card)
        if n_val > hv:
            # print("take new card")
            self.hand, self.deck.discard = n_hand, n_disc
            # todo we may feed our op 7/8/9/face if we draw a suited low card
        else:
            # print("discard new card")
            self.deck.discard = new_card

        assert self.deck.size() + len(self.deck.pile) == 52 - 3 * PLAYER_CNT - 1

        return


class Statistics:
    def __init__(self) -> None:
        self.entries = []
        self.records_folder = "records"
        if not os.path.exists(self.records_folder):
            os.makedirs(self.records_folder)

    def update(self, players_arr: list[Player]):
        entry = dict(
            winner=argmax([p.hand_value() for p in players_arr]),
            turns=len(self.entries) + 1,
        )

        for i, player in enumerate(players_arr):
            entry[f"{i}_hand"] = str(player.hand)
            entry[f"{i}_val"] = player.hand_value()

        self.entries.append(entry)

    def dump(self):
        if not self.entries:
            print("No data to export.")
            return

        file_number = 0
        fname = None
        while os.path.exists(
            fname := os.path.join(self.records_folder, f"{file_number}.csv")
        ):
            file_number += 1
            # and they say you cannot do-while in py

        with open(fname, "w", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=list(self.entries[0].keys()))
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry)
        print(f"Data exported to {fname}")


if __name__ == "__main__":
    # for _ in trange(100000):
    #     pa = Player(Deck())
    #     # print(pa.hand, pa.hand_value_suited())
    #     assert pa.hand_value() == pa.hand_value_suited()[0]
    stats = Statistics()

    for itr in trange(SAMPLES):  # todo parallelize
        deck = Deck()
        # print(deck)
        players_arr = [Player(deck) for _ in range(PLAYER_CNT)]
        assert deck.size() == 52 - 3 * PLAYER_CNT - 1

        active = 0
        turns = 0

        while (pa := players_arr[active]) and not pa.is_over:
            assert deck.size() + len(deck.pile) == 52 - 3 * PLAYER_CNT - 1

            pa.turn()
            turns += 1

            active = (active + 1) % PLAYER_CNT

        stats.update(players_arr)
    stats.dump()
