import sys, types

mod = types.ModuleType('src.backend.sitesearch.handler.base_handler')
class BaseHandler: 
    pass
class ComponentStatus:
    STOPPED = 'stopped'
    RUNNING = 'running'
mod.BaseHandler = BaseHandler
mod.ComponentStatus = ComponentStatus
sys.modules['src.backend.sitesearch.handler.base_handler'] = mod
