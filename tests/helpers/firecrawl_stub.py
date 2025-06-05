import sys, types

firecrawl_mod = types.ModuleType('firecrawl')
sub_mod = types.ModuleType('firecrawl.firecrawl')

class FirecrawlApp:
    def __init__(self, *args, **kwargs):
        pass

class ScrapeOptions: ...
class CrawlStatusResponse: ...
class FirecrawlDocument: ...
class CrawlResponse: ...
class ScrapeResponse: ...

sub_mod.FirecrawlApp = FirecrawlApp
sub_mod.ScrapeOptions = ScrapeOptions
sub_mod.CrawlStatusResponse = CrawlStatusResponse
sub_mod.FirecrawlDocument = FirecrawlDocument
sub_mod.CrawlResponse = CrawlResponse
sub_mod.ScrapeResponse = ScrapeResponse

firecrawl_mod.firecrawl = sub_mod

sys.modules['firecrawl'] = firecrawl_mod
sys.modules['firecrawl.firecrawl'] = sub_mod
