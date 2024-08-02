import pandas as pd
import random as r
from datetime import datetime
from scipy.stats import skewnorm
import logging

# curtural_facilities.csv, festivals.csv, leisure_sports.csv, tourist_spots.csv
# 4개 파일의 contentsid를 받아 랜덤 리뷰 데이터를 생성해 반환하는 함수
def ReviewDataGenerator(all_tour_data):
    today_num_of_review = r.randint(500, 800)
    review_df = pd.DataFrame(columns=['UserID', 'TouristSpotID', 'Title', 'Timestamp', 'Score', 'Category'])
    for i in range(today_num_of_review):
        try:
            # UserID
            userid = r.randint(0,100000000)
            
            try:
                # Randomly select a tour data (pair of contentid and title, and category)
                tour_data = r.choice(all_tour_data)
                tourid = tour_data['contentid']
                title = tour_data['title']
                category = tour_data['category']
            except Exception as e:
                logging.error(f"Error - tour data: {e}")
                return
            
            try:
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
            except Exception as e:
                logging.error(f"Error - timestamp: {e}")
                return
            
            try:
                # Score
                a, loc, scale = 2, 50, 12
                score = int(skewnorm(a, loc, scale).rvs(1)[0])
                score = max(0, min(score, 100))
            except Exception as e:
                logging.error(f"Error - score: {e}")
                return

            try:
                # 데이터 추가
                review = pd.DataFrame({
                    'UserID': [userid],
                    'TouristSpotID': [tourid],
                    'Title': [title],
                    'Timestamp': [timestamp],
                    'Score': [score],
                    'Category': [category]
                })
                review_df = pd.concat([review_df, review])
            except Exception as e:
                logging.error(f"Error - dataframe: {e}")
                return

        except Exception as e:
            logging.error(f"Error is occurred while creating reviews: {e}")
            return
    
    review_df = review_df.sort_values(by=['Timestamp'], axis=0).reset_index(drop=True)
    logging.info(f"Review data was successfully created: {review_df[:10]}")
    return review_df