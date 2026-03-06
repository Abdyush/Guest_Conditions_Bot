from core.ports import OffersSiteGateway, OffersRepository

class OfferParsingService:
    def __init__(self, gateway: OffersSiteGateway, repo: OffersRepository):
        self.gateway = gateway
        self.repo = repo

    def parse_offers(self):
        print("[trace] OfferParsingService.parse_offers start")
        offers = self.gateway.get_all_offers()
        print(f"[trace] parsed {len(offers)} offers")
        for offer in offers:
            self.repo.save_offer(offer)
        print("[trace] OfferParsingService.parse_offers done")
            