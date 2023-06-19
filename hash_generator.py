import streamlit_authenticator as stauth
hashed_passwords = stauth.Hasher(['']).generate()
print(hashed_passwords)