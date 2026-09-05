from typing import List, Dict

class SimulatedTradingEngine:
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.portfolio: Dict[str, int] = {}
        self.active_orders: List[Dict] = []
        self.order_id_counter = 1

    def submit_order(self, side: str, item_id: str, quantity: int, limit_price: float) -> int:
        """
        Submit a virtual buy or sell order.
        side should be 'buy' or 'sell'
        """
        if side not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")

        if limit_price <= 0:
            raise ValueError("Limit price must be greater than 0")

        order_id = self.order_id_counter
        self.order_id_counter += 1

        self.active_orders.append({
            "order_id": order_id,
            "side": side.lower(),
            "item_id": item_id,
            "quantity": quantity,
            "limit_price": limit_price,
            "filled": 0
        })
        return order_id

    def match_against_listings(self, listings: List[Dict]):
        """
        Match active orders against live market prices (listings).
        Listings are assumed to be a list of dictionaries, each having 'item_id' and 'price'.
        """
        # For buy orders: we can buy if a listing's price <= our limit price
        # For sell orders: since the market provides 'sell' listings, we might match our sell orders
        # if our sell limit price <= market price metric (e.g. median or we just use market sell listings as a proxy for what gets bought).
        # Alternatively, we could assume sell orders get filled if there's a listing with price >= our limit price?
        # Actually, if the lowest market sell listing is ABOVE our limit price, it means our sell listing is the cheapest on the market,
        # so it would likely be bought first. Or maybe we just match sell orders against ANY market activity that indicates a price >= our limit price.
        # Let's do a simple approach:
        # - Buy order: Fill against a specific listing where listing_price <= limit_price. We consume that listing.
        # - Sell order: Fill if any listing exists with listing_price >= limit_price (implying market is trading at or above our price).
        # Wait, if we want to be realistic:
        # A buy order takes liquidity (buys from existing sell listings).
        # A sell order provides liquidity (adds a sell listing). It gets filled if someone buys it.
        # Since we only observe sell listings, we can assume our sell order is filled if the lowest observed sell listing price > our limit price (we would have been bought first), OR if we just use the price of listings as a proxy for "market price".
        # Let's just say a sell order is filled if there is a listing with price >= our limit price (as a simple proxy for market trading at that price).
        # Let's implement this.

        # Sort listings by price ascending to simulate taking the best offers first
        sorted_listings = sorted([lst for lst in listings if lst.get('price') is not None and lst.get('item_id') is not None], key=lambda x: x['price'])

        listings_used = set()
        new_active_orders = []

        for order in self.active_orders:
            remaining_qty = order["quantity"] - order["filled"]

            if remaining_qty <= 0:
                continue

            if order["side"] == "buy":
                # Buy from cheapest listings that are <= limit_price
                for i, listing in enumerate(sorted_listings):
                    if i in listings_used:
                        continue
                    if listing["item_id"] == order["item_id"] and listing["price"] <= order["limit_price"]:
                        # Match!
                        # Assume each listing has quantity=1 for simplicity if not specified
                        listing_qty = listing.get("quantity", 1)
                        fill_qty = min(remaining_qty, listing_qty)

                        fill_price = listing["price"]
                        cost = fill_price * fill_qty

                        if self.balance >= cost:
                            self.balance -= cost
                            order["filled"] += fill_qty
                            remaining_qty -= fill_qty

                            self.portfolio[order["item_id"]] = self.portfolio.get(order["item_id"], 0) + fill_qty

                            # Update listing quantity or mark as used
                            if listing_qty <= fill_qty:
                                listings_used.add(i)
                            else:
                                listing["quantity"] = listing_qty - fill_qty

                        if remaining_qty <= 0:
                            break

            elif order["side"] == "sell":
                # Sell if the market is trading at or above our limit price.
                # We can proxy this by checking if there's any listing >= limit_price.
                # Or better, if the current cheapest listing is >= limit_price, we definitely would have been bought.
                # Let's just find any listing for this item to determine market condition.
                item_listings = [lst for lst in sorted_listings if lst["item_id"] == order["item_id"]]
                if item_listings:
                    # If we placed a sell order at limit_price, and market price is at least limit_price, we get filled.
                    # As a simplistic model, we'll fill the whole order if the condition is met.
                    # Or fill quantity based on some market volume. Let's just fill completely if cheapest listing >= limit_price.
                    cheapest_price = item_listings[0]["price"]
                    if cheapest_price >= order["limit_price"]:
                        available_qty = self.portfolio.get(order["item_id"], 0)
                        fill_qty = min(remaining_qty, available_qty)
                        if fill_qty > 0:
                            revenue = order["limit_price"] * fill_qty
                            self.balance += revenue
                            order["filled"] += fill_qty
                            remaining_qty -= fill_qty
                            self.portfolio[order["item_id"]] -= fill_qty

            if order["filled"] < order["quantity"]:
                new_active_orders.append(order)

        self.active_orders = new_active_orders


    def get_pnl(self, current_market_prices: Dict[str, float] = None) -> Dict[str, float]:
        """
        Calculate realized and unrealized PnL.
        realized_pnl = current cash balance - initial balance
        unrealized_pnl = value of portfolio at current market prices
        total_pnl = realized + unrealized
        """
        if current_market_prices is None:
            current_market_prices = {}

        realized_pnl = self.balance - self.initial_balance

        portfolio_value = 0.0
        for item_id, qty in self.portfolio.items():
            if qty > 0:
                price = current_market_prices.get(item_id, 0.0)
                portfolio_value += qty * price

        unrealized_pnl = portfolio_value
        total_pnl = realized_pnl + unrealized_pnl

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "portfolio_value": portfolio_value,
            "cash_balance": self.balance
        }
