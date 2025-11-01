class MatchingConfig:
    TEXT_TOP_K = 20          
    IMAGE_TOP_K = 20          
    FINAL_CANDIDATES = 30    
    
 
    TEXT_WEIGHT = 0.45
    IMAGE_WEIGHT = 0.35
    STRUCTURED_WEIGHT = 0.20
    
    MAX_WORKERS = 4          
    IMAGE_TIMEOUT = 5        
    MAX_IMAGES_PER_LISTING = 2  
    
    @classmethod
    def fast_mode(cls):
        cls.TEXT_TOP_K = 10
        cls.IMAGE_TOP_K = 10
        cls.FINAL_CANDIDATES = 15
        cls.IMAGE_WEIGHT = 0.2  
        cls.TEXT_WEIGHT = 0.6  
        cls.STRUCTURED_WEIGHT = 0.2