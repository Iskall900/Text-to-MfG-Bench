**Reported 1st Mode VS Fusion 1st mode**

- Line y=x through graph to show overeporting
- Really only applicable if model’s setup FEA themselves.

**Trial run cost vs. composite score**

**Artificial analysis index intelligence score vs. composite score**

**Number of fea iterations vs 1st mode, vs model.**

**Question - What is the correlation between how many times a model uses FEA and its 1st mode results?**

- Do certain models tend to use fea more than others?

**4.2: FEA calls per model, as a box plot.**

- Kruskal-Wallis on FEA calls across models, then pairwise Mann-Whitney with BH correction.

**4.1: FEA calls vs 1st mode, as a scatter colored by model.**

**Time vs composite performance w/model labels**

- Time varies with provider tps, so more informative than statistical

**Reasoning+output tokens vs performance w/model labels**

- Log scale for x (tokens)

**Success rate per model**

- Bar graph
- Fisher's exact test

**Compositite score per model w/AGD composite score as line**

- Box+whisker plot for median score, q1, q3, and max+min which are important data points.
- Mean marker
- Successful trials as dots
- Kruskal-Wallis to see if models differ at all, p<0.05 says at least one model differs
- Pairwise mann-whitney U compares models two at a time, Benjamini-Hochberg correction to lower the chance of error
- One sample wilcoxon to see if a single model beats AGD
