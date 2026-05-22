from sklearn.ensemble import RandomForestRegressor
#scale invariant hota h
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,OrdinalEncoder
from sklearn.model_selection import train_test_split, KFold, RandomizedSearchCV
from sklearn.metrics import r2_score,mean_squared_error
import pandas as pd
import joblib


df = pd.read_csv("insurance_risk_dataset_5000.csv")
x = df.drop(columns=['risk_score'])
y = df['risk_score']
print('created data')
binary_cols = ['gender','smoker','marital_status','chronic_disease']
nominal_cols = ['occupation','city']
ordinal_cols = ["income_category", "exercise_frequency","alcohol_consumption"]

income_order = ["Low","Lower Middle", "Middle", "Upper Middle", "High"]
exercise_order = ["Never", "Rarely", "Weekly", "Daily"]
alcohol_order = ["None","Occasional","Frequent"]

print("initializing preprocessing")
preprocessor = ColumnTransformer(
    transformers=[
        ('bin',OneHotEncoder(handle_unknown="ignore",drop="if_binary"),binary_cols),
        ('nom',OneHotEncoder(handle_unknown="ignore"),nominal_cols),
        ('ord',OrdinalEncoder(categories=[income_order, exercise_order, alcohol_order],
            handle_unknown="use_encoded_value",
            unknown_value=-1),
            ordinal_cols)
    ],
    remainder='passthrough'
)
print('transformed')


x_train,x_test,y_train,y_test = train_test_split(x,y,random_state=42,test_size=0.3,shuffle=True)
kf = KFold(n_splits=5,random_state=42,shuffle=True)
pipe = Pipeline([
    ('preprocessor',preprocessor),
    ('model',RandomForestRegressor(bootstrap=True,random_state=42,n_estimators=200))
])
param_grid = {
    'model__criterion':['squared_error','friedman_mse','absolute_error'],
    'model__max_depth':[2,3,5,7,9,10,12,None],
    'model__min_samples_split':[2,3,4,5,7,9],
    'model__min_samples_leaf':[1,2,3,4,5,7,8]
}
grid  = RandomizedSearchCV(
    pipe,
    param_grid,
    n_iter=150,
    scoring='r2',
    cv=kf,
    n_jobs=-1,
    random_state=42,
)
grid.fit(x_train,y_train)
print("model is fitted")
print(grid.best_score_)
print(grid.best_params_)
best_model = grid.best_estimator_
print(best_model.score(x_test,y_test))
y_pred = best_model.predict(x_test)
print(r2_score(y_test,y_pred))
print(mean_squared_error(y_test,y_pred))

joblib.dump(best_model,'best_model.pk1')