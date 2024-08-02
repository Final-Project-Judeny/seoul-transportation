import pandas as pd
import random as r
from datetime import datetime
from scipy.stats import skewnorm
import logging

# curtural_facilities.csv, festivals.csv, leisure_sports.csv, tourist_spots.csv
# 4개 파일의 contentsid를 받아 랜덤 리뷰 데이터를 생성해 반환하는 함수
def ReviewDataGenerator(all_tour_id):
    today_num_of_review = r.randint(500, 800)
    review_df = pd.DataFrame(columns=['UserID', 'TouristSpotID', 'Timestamp', 'Score'])
    for i in range(today_num_of_review):
        # UserID
        userid = r.randint(0,100000000)
        
        # TouristSpotID
        tourid = r.choice(all_tour_id)
        
        # Timestamp
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = r.randint(0, 23)
        minute = r.randint(0, 59)
        second = r.randint(0, 59)
        logging.info(f"{year}-{month}-{day} {hour}:{minute}:{second}")
        timestamp = datetime(year, month, day, hour, minute, second).strftime('%Y%m%d%H%M%S')
        
        # Score
        a, loc, scale = 2, 50, 12
        score = int(skewnorm(a, loc, scale).rvs(1)[0])
        if score > 100:
            score = 100
        elif score < 0:
            score = 0

        # 데이터 추가
        review = pd.DataFrame({
            'UserID': [userid],
            'TouristSpotID': [tourid],
            'Timestamp': [timestamp],
            'Score': [score]
        })
        review_df = pd.concat([ review_df, review ])
    
    review_df = review_df.sort_values(by=['Timestamp'], axis=0).reset_index(drop=True)
    logging.info(f"Review data was successfully created: {review_df[:10]}")
    return review_df