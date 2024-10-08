import pandas as pd
import random as r
from datetime import datetime
from scipy.stats import skewnorm
import logging

# curtural_facilities.csv, festivals.csv, leisure_sports.csv, tourist_spots.csv
# 4개 파일의 contentsid를 받아 랜덤 리뷰 데이터를 생성해 반환하는 함수
def ReviewDataGenerator(all_tour_data, date):
    today_num_of_review = r.randint(40, 60)
    review_df = pd.DataFrame(columns=['UserID', 'TouristSpotID', 'Title', 'Timestamp', 'Score'])
    for i in range(today_num_of_review):
        try:
            # UserID
            userid = r.randint(0,100000000)
            
            # Randomly select a tour data (pair of contentid and title, and category)
            tour_data = r.choice(all_tour_data)
            tourid = tour_data['contentid']
            title = tour_data['title']
        
            # Timestamp
            now = list(map(int, date.split('-')))
            year = now[0]
            month = now[1]
            day = now[2]
            hour = r.randint(0, 23)
            minute = r.randint(0, 59)
            second = r.randint(0, 59)
            timestamp = datetime(year, month, day, hour, minute, second).isoformat()
        
            # Score
            a, loc, scale = 2, 50, 12
            score = int(skewnorm(a, loc, scale).rvs(1)[0])
            score = max(0, min(score, 100))

            # 데이터 추가
            review = pd.DataFrame({
                'UserID': [userid],
                'TouristSpotID': [tourid],
                'Title': [title],
                'Timestamp': [timestamp],
                'Score': [score],
            })
            review_df = pd.concat([review_df, review])

        except Exception as e:
            logging.error(f"Error is occurred while creating reviews: {e}")
            return
    
    review_df = review_df.sort_values(by=['Timestamp'], axis=0).reset_index(drop=True)
    logging.info(f"Review data was successfully created: {review_df[:10]}")
    return review_df