# Deploy checklist (Streamlit Community Cloud)

1. On GitHub, create an EMPTY repository (no README, no license).
2. On your machine, in the unzipped project folder:
   ```
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
   (Commits are authored as "Amith Gowda S <noreply@example.com>". Run
   `git config user.email you@example.com` and rewrite if you want your real address.)
3. Confirm the GitHub Actions run is green. It runs `pip install -r requirements-dev.txt` then `pytest -q`.
   This is the FIRST real pytest run: the build sandbox had no network, so pytest was never run there.
4. On share.streamlit.io: New app -> pick the repo -> branch `main` -> main file `app.py` -> Deploy.
5. Smoke-test the live app with each built-in example and the three dialect choices. The Streamlit calls in
   `app.py` were only tested against a stub, so check the real page renders and the download button works.
6. Do NOT add the live URL to the portfolio site until step 5 passes.
