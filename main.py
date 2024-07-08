from typing import List, Tuple
import random
from tqdm import tqdm, trange


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


def all_but_idx(lst, idx):
    return lst[:idx] + lst[idx + 1 :]


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
            self.cards, self.pile = self.pile, []
            self.shuffle()
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

        # this could be refactored to show decision tree; ensuring we handle all cases
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

        # ! bad -- ties broken arbitarily !
        for i in range(len(self.hand)):
            test_hand = [card] + all_but_idx(self.hand, i)
            # test_hand = [card] + self.hand[i + 1 :] + self.hand[:i]
            if (test_val := self.hand_value(test_hand)) > val:
                val, hand = test_val, test_hand
                disc = self.hand[i]
        return val, hand, disc

    @property
    def is_over(self) -> bool:
        return self.down or self.hand_value() == 31

    def turn(self):
        assert not self.is_over  # (we are so back)
        hv, hs = self.hand_value_suited()
        is_hero = self.id == HERO

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
                self.hand, self.deck.discard = d_hand, d_disc
                return

        new_card = self.deck.draw()
        n_val, n_hand, n_disc = self.best_value_given_card(new_card)
        if n_val > hv:
            # todo we may feed our op 7/8/9/face if we draw a suited low card
            self.hand, self.deck.discard, n_hand, n_disc
            self.deck.pile.append(new_card)
            return

        self.deck.discard = new_card
        return


if __name__ == "__main__":
    PLAYERS = 3
    HERO = 0  # compare w randomization
    THRESHOLD = 22

    deck = Deck()
    # print(deck)
    players = [Player(deck) for _ in range(PLAYERS)]
    assert deck.size() == 52 - 3 * PLAYERS - 1

    # for _ in trange(100000):
    #     pa = Player(Deck())
    #     # print(pa.hand, pa.hand_value_suited())
    #     assert pa.hand_value() == pa.hand_value_suited()[0]

    active = 0
    turns = 0

    while True:
        pa = players[active]

        if pa.is_over:
            pv = pa.hand_value()
            if pv == 31 or pv > (
                better := max([op.hand_value() for op in all_but_idx(players, active)])
            ):
                print(f"{active} won after {turns} with {pv}")
                # todo print stats
            else:
                print(f"{active} was beat  after {turns} with {pv} to {better}")
            break
        pa.turn()

        active = (active + 1) % PLAYERS
        turns += 1
