#!/usr/bin/python3

from get_odds import get_todays_odds
from data import LeagueStats
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd  # type: ignore
import statsapi  # type: ignore

MODELS = ["mlb3year", "mlb2023", "mets6year"]
global_correct = 0
global_wrong = 0
mlb = LeagueStats()


def update_row(row: pd.Series) -> pd.Series:
    """
    function to update the row data of completed games

    Args:
        row: Row data as a pandas Series object.

    Returns:
        updated_row: The updated row with prediction accuracy and other information.
    """
    global global_correct, global_wrong
    predicted_winner = row["predicted_winner"]
    id = row["game_id"]
    game = statsapi.schedule(game_id=id)[0]
    if game["status"] != "Final":
        return row
    actual_winner = game.get("winning_team")
    prediction_accuracy = (
        1.0
        if (actual_winner == predicted_winner)
        else (0.0 if actual_winner is not None else None)
    )
    losing_team = row["home"] if actual_winner == row["away"] else row["away"]
    if prediction_accuracy == 1.0:
        global_correct += 1
        print(
            f"Correct! Your prediction - {predicted_winner} - "
            f"defeated the {losing_team}."
        )
    else:
        global_wrong += 1
        print(
            f"Wrong! Your prediction - {predicted_winner} - "
            f"lost to the {actual_winner}."
        )
    updated_row = row.copy()
    # update any row information that you want knowing the game is complete
    updated_row["prediction_accuracy"] = prediction_accuracy
    updated_row["home_score"] = game["home_score"]
    updated_row["away_score"] = game["away_score"]
    updated_row["winning_pitcher"] = game["winning_pitcher"]
    updated_row["losing_pitcher"] = game["losing_pitcher"]
    updated_row["datetime"] = game.get("datetime")
    updated_row["game_id"] = game["game_id"]
    updated_row["summary"] = game["summary"]
    return updated_row


def load_unchecked_predictions_from_excel(
    file_name: str,
) -> Optional[pd.DataFrame]:
    """
    function to load unchecked predictions from the excel sheet back into pd dataframe
        -> i.e. predictions that don't yet have an input for prediction_accuracy

    Args:
        file_name: string file name to retrieve past predictions from (.xlsx)

    Returns:
        df: data frame with past predictions
    """
    try:
        df = pd.read_excel(file_name)
        df_missing_accuracy = df[df["prediction_accuracy"].isnull()]
        df_missing_accuracy = df_missing_accuracy.apply(update_row, axis=1)
        if (global_correct + global_wrong) > 0:
            percentage = global_correct / (global_correct + global_wrong)
            print(
                f"Prediction accuracy for recently checked games: "
                f"{str(global_correct)}/{str(global_wrong + global_correct)} "
                f"({int(100 * (round(percentage, 2)))}%)"
            )
        df.update(df_missing_accuracy)
        df.to_excel(file_name, index=False)
        return df
    except FileNotFoundError:
        return None


def generate_daily_predictions(
    model: str, date: datetime = datetime.now()
) -> List[Dict]:
    """
    function to generate predictions for one day of MLB games...
    ...and save them with other pertinent game information

    Args:
        model: model to use
            -> must be defined in MODELS
        date: datetime object representing day to predict on

    Returns:
        game_predictions: list of dictionaries with prediction + odds information
    """
    if date is not datetime.now():
        # NOT IMPLEMENTED: generating predictions for future days
        pass
    file_name = "./data/predictions.xlsx"

    try:
        df = pd.read_excel(file_name)
        existing_dates = pd.to_datetime(df["datetime"]).dt.date.unique()
        if date.date() in existing_dates:
            mask = (pd.to_datetime(df["datetime"]).dt.date == date.date()) & (
                pd.to_datetime(df["prediction_generation_time"]).dt.date == date.date()
            )
            filtered_df = df[mask]
            if len(filtered_df) > 0:
                predictions = filtered_df.to_dict("records")
                return predictions
            else:
                new_mask = pd.to_datetime(df["datetime"]).dt.date == date.date()
                df = df[~new_mask]
    except FileNotFoundError:
        df = pd.DataFrame()

    all_games, odds_time = get_todays_odds()
    game_predictions: List[Dict] = []
    for game in all_games:
        try:
            ret = mlb.predict_next_game("mlb2023", game["home_team"])
            if ret is None or ret[0] is None:
                continue
            winner, prediction, info = ret[0], ret[1], ret[2]
        except Exception as _:
            continue
        if not winner:
            continue
        home, away = info["home"], info["away"]
        info["predicted_winner"] = winner
        info["model"] = model
        info["predicted_winner_location"] = "home" if (winner is home) else "away"
        info["prediction_value"] = prediction
        info["time"] = game["time"]
        info["favorite"] = game.get("favorite")
        info["home_odds"] = game.get(f"{home}_odds")
        info["away_odds"] = game.get(f"{away}_odds")
        info["home_odds_bookmaker"] = game.get(f"{home}_bookmaker")
        info["away_odds_bookmaker"] = game.get(f"{away}_bookmaker")
        info["odds_retrieval_time"] = odds_time
        info["prediction_generation_time"] = datetime.now()
        info["prediction_accuracy"] = None
        info["home_score"] = None
        info["away_score"] = None
        info["winning_pitcher"] = None
        info["losing_pitcher"] = None
        game_predictions.append(info)

    df_new = pd.DataFrame(game_predictions)
    column_order = [
        "prediction_accuracy",
        "date",
        "time",
        "home",
        "home_probable",
        "away",
        "away_probable",
        "predicted_winner",
        "model",
        "favorite",
        "home_odds",
        "home_odds_bookmaker",
        "away_odds",
        "away_odds_bookmaker",
        "home_score",
        "away_score",
        "winning_pitcher",
        "losing_pitcher",
        "prediction_value",
        "venue",
        "series_status",
        "national_broadcasts",
        "odds_retrieval_time",
        "prediction_generation_time",
        "datetime",
        "game_id",
        "summary",
    ]
    df_new = df_new[column_order]
    df = pd.concat([df, df_new], ignore_index=True)
    df.to_excel(file_name, index=False)

    return game_predictions


def main():
    file_name = "./data/predictions.xlsx"
    try:
        df = load_unchecked_predictions_from_excel(file_name)
    except Exception as e:
        print(f"Error checking past predictions in {file_name}. {e}")

    model_list = ", ".join([str(item) for item in MODELS])
    model = input(f"Select model to make today's predictions ({model_list}): ")
    success = False
    while not success:
        if model in MODELS:
            success = True
        else:
            model = input(
                f"{model} is not a valid model. "
                f"Please choose one of the following: {model_list}. "
            )
            success = False
    print(f"Making predictions using {model} model!")
    generate_daily_predictions(model)


if __name__ == "__main__":
    main()
