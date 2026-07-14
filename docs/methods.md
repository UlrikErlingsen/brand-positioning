# Methods and interpretation

PositionSignal turns ratings on named brand attributes into a two-dimensional perceptual map. The map is a compact description of the selected brands and attributes; it is not a universal market truth, a causal model, or evidence that consumers naturally think in exactly two dimensions.

## Unit of analysis

The fitted matrix has one row per brand and one column per attribute. If the upload already has one aggregate row per brand, those values are used directly. If the upload contains respondent-brand rows, PositionSignal first calculates a brand mean for each attribute. This aggregate-first design makes the axes describe **between-brand positioning**. Fitting the axes to every individual rating row instead would allow within-brand respondent noise to determine the map.

For brand \(b\), attribute \(a\), valid ratings \(y_{rba}\), and optional respondent weight \(w_r\), the profile value is

\[
m_{ba}=\frac{\sum_r w_r y_{rba}}{\sum_r w_r}.
\]

Without a selected weight column, every valid rating has weight 1. The app also records ordinary cell counts. With weights it reports the Kish effective base

\[
n^{\mathrm{eff}}_{ba}=\frac{(\sum_r w_r)^2}{\sum_r w_r^2},
\]

which exposes how unequal weights reduce the information in a nominal sample. This is a descriptive effective base, not a full complex-survey variance estimator.

Respondent-level blanks are omitted from the corresponding cell mean. A brand-attribute cell with no usable observation remains missing: PositionSignal never fills it with an invented mean. Depending on the selected policy, an incomplete attribute either stops the analysis or is removed in full. Attributes that do not vary between brands are also removed because they cannot define a direction.

## Preparation

The default is correlation-style PCA: each attribute is centered and divided by its sample standard deviation across the \(B\) brands,

\[
z_{ba}=\frac{m_{ba}-\bar m_{\cdot a}}{s_a},
\qquad
s_a=\sqrt{\frac{1}{B-1}\sum_b(m_{ba}-\bar m_{\cdot a})^2}.
\]

This gives every selected attribute equal starting variance, so a 1-to-7 item and a 0-to-100 item cannot dominate merely because of their units. It also means that an attribute with little absolute brand separation receives the same initial weight as a more dispersed attribute. The advanced center-only option preserves original dispersion and is defensible only when the measures share meaningful units and their observed variance should determine influence.

Highly correlated or duplicated attributes are not statistically invalid, but they give the repeated concept extra influence. Attribute selection is therefore part of the model, not clerical setup.

## Principal components

Let \(X\) be the complete centered or standardized brand-profile matrix. PositionSignal uses a deterministic full singular-value decomposition,

\[
X=UDV^\top.
\]

The complete brand score matrix is \(T=UD\). Component \(k\) has eigenvalue and explained share

\[
\lambda_k=\frac{d_k^2}{B-1},
\qquad
e_k=\frac{\lambda_k}{\sum_j\lambda_j}.
\]

The displayed map uses the first two score columns. PCA signs are mathematically arbitrary, so PositionSignal makes exports reproducible by finding the strongest absolute coefficient on each component and orienting that coefficient positively. If several coefficients tie, the lexicographically first attribute anchors the sign. Mirroring an axis would not change distances or substantive relationships.

The axis helper text lists strongly associated attributes on both sides. It is an orientation aid, not an estimated name for a latent construct. `PC1` and `PC2` remain the honest axis names.

## The row-metric biplot

The rank-two approximation is

\[
X_{(2)}=T_{(2)}V_{(2)}^\top.
\]

Brands therefore use ordinary PCA scores. Their Euclidean distances on the map are the two-dimensional projections of their distances in the complete analysis space. Attribute arrows use the matching PCA coefficients. To make points and arrows legible on one plot, PositionSignal applies reciprocal scalar scaling,

\[
G=T_{(2)}/c,
\qquad
H=cV_{(2)},
\]

where \(c\) balances the largest brand and arrow radii. Because \(GH^\top=T_{(2)}V_{(2)}^\top\), the displayed inner-product reconstruction is unchanged, and every brand distance receives only the same harmless display multiplier. The app never stretches the two axes independently.

On this map:

- nearby brands have similar profiles in the displayed two-dimensional projection; full-profile distances must be checked before calling two brands close overall;
- the origin is the average profile of the selected competitor set;
- an arrow points toward increasing reconstructed values of its attribute;
- a brand in an arrow's direction tends to rate relatively high on that attribute;
- quadrants have no inherent strategic meaning.

Attribute-arrow angles on the main row-metric map should not be read as literal correlations. For that purpose, PositionSignal provides a separate correlation circle. For standardized PCA, the correlation loading is

\[
L_{ak}=\operatorname{corr}(X_{\cdot a},T_{\cdot k})
=\sqrt{\lambda_k}V_{ak}.
\]

On the unit correlation circle, arrows in similar directions indicate positive association, opposite arrows indicate negative association, and near-right angles indicate weak linear association within the selected brand set.

## Representation and influence diagnostics

### Variance retained

The headline two-dimensional retention is \(e_1+e_2\). It answers how much squared variation in the complete prepared profile matrix survives the projection. It is not a test of market validity. The interface uses cautious descriptive language when the map retains little structure.

### Brand representation (cosine squared)

For brand \(b\),

\[
\cos_b^2=\frac{t_{b1}^2+t_{b2}^2}{\sum_k t_{bk}^2}.
\]

This is the share of that brand's squared displacement from the market center represented in the picture. A low value means the plotted location omits important higher-dimensional information. A brand exactly at the center has no direction to represent, so its value is undefined.

The brand's contribution to component \(k\) is

\[
\operatorname{ctr}_{bk}=\frac{t_{bk}^2}{\sum_b t_{bk}^2}.
\]

Large contributions identify brands that strongly orient an axis; they are not quality scores.

### Attribute representation and influence

For a standardized attribute,

\[
\cos_a^2=L_{a1}^2+L_{a2}^2.
\]

This measures how well the two axes reproduce its variation. The coefficient contribution to component \(k\) is \(V_{ak}^2\); contributions sum to one down each component.

### Distance fidelity

PositionSignal compares every full-space Euclidean brand distance \(d_{ij}\) with its projected distance \(\hat d_{ij}\). It reports their correlation and normalized distance error

\[
\sqrt{\frac{\sum_{i<j}(d_{ij}-\hat d_{ij})^2}
{\sum_{i<j}d_{ij}^2}}.
\]

The closest-competitor ranking deliberately uses **full-space distance**, not visual proximity alone. Pair exports include both distances and the retained fraction \(\hat d_{ij}/d_{ij}\).

### Eigengaps

The diagnostics report

\[
g_{12}=\frac{\lambda_1-\lambda_2}{\lambda_1}
\quad\text{and}\quad
g_{23}=\frac{\lambda_2-\lambda_3}{\lambda_2}
\]

when a third component exists. A small \(g_{12}\) means the individual PC1/PC2 directions may rotate inside an otherwise useful plane. A small \(g_{23}\) means the two-dimensional plane itself competes with a third direction. These are stability clues, not pass/fail tests.

## Respondent-cluster bootstrap

Aggregate profiles alone contain no information about respondent sampling variation, so PositionSignal does not manufacture confidence regions for aggregate-only files.

When respondent IDs are available, each bootstrap iteration samples respondent IDs with replacement and carries **all rows belonging to the sampled respondent** together. This preserves dependence when the same person rated several brands. When respondents belong to independent brand-specific samples, resampling is performed within brand so each brand's sample size is preserved. The app then repeats aggregation, preparation, and PCA from the beginning. Survey weights remain attached to their respondents. At least two independent respondents are required in every included brand–attribute cell; bases below 10 receive a caution.

Bootstrap axes may flip, swap, or rotate even when the underlying configuration is similar. PositionSignal estimates an orthogonal Procrustes rotation from the bootstrap and reference loading matrices, then applies the same rotation to the centered bootstrap brand scores. Reflection and rotation are allowed; scale dilation is not. The aligned cloud for each brand supplies a covariance matrix, from which the app draws the requested chi-squared ellipse around the bootstrap-cloud mean.

These are **bootstrap uncertainty regions conditional on the selected respondents, brands, attributes, weighting, and preprocessing**. They are not prediction regions, and overlapping or non-overlapping ellipses are not a formal significance test. A complex survey may require stratified, clustered, replicate-weight, or finite-population methods beyond this release. Sparse designs can generate unusable bootstrap maps; PositionSignal reports successful iterations and refuses to draw regions when too few refits succeed.

## Boundaries

- At least three usable brands and two varying attributes are required. With exactly three brands, centered rank is at most two, so 100% displayed variance is automatic rather than evidence of a strong map.
- A numerically one-dimensional profile matrix is not forced into a two-axis picture.
- Treating rating scales as numeric assumes their steps are useful approximate intervals. This is conventional for aggregated multi-item market research, but it remains an assumption.
- PCA describes linear structure. Curved or respondent-specific perceptual spaces may need other methods.
- Broadly positive PC1 associations can represent general favorability or halo. PositionSignal describes that pattern rather than automatically removing it.
- Results are conditional on the competitive frame. Adding a brand or attribute changes column centers, standard deviations, and potentially the axes.
- PCA has no privileged quadrant labels and provides no causal or market-share conclusions.
- High explained variance does not repair biased samples, vague attributes, low awareness, or poor questionnaire design.

## Primary references

- Gabriel, K. R. (1971). The biplot graphic display of matrices with application to principal component analysis. *Biometrika, 58*(3), 453-467. [https://doi.org/10.1093/biomet/58.3.453](https://doi.org/10.1093/biomet/58.3.453)
- Schönemann, P. H. (1966). A generalized solution of the orthogonal Procrustes problem. *Psychometrika, 31*, 1-10. [https://doi.org/10.1007/BF02289451](https://doi.org/10.1007/BF02289451)
- Babamoradi, H., van den Berg, F., & Rinnan, Å. (2013). Bootstrap based confidence limits in principal component analysis-A case study. *Chemometrics and Intelligent Laboratory Systems, 120*, 97-105. [https://doi.org/10.1016/j.chemolab.2012.10.007](https://doi.org/10.1016/j.chemolab.2012.10.007)
- Steenkamp, J.-B. E. M., van Trijp, H. C. M., & ten Berge, J. M. F. (1994). Perceptual mapping based on idiosyncratic sets of attributes. *Journal of Marketing Research, 31*(1), 15-27. [https://doi.org/10.1177/002224379403100102](https://doi.org/10.1177/002224379403100102)
- Bijmolt, T. H. A., & van de Velden, M. (2012). Multiattribute perceptual mapping with idiosyncratic brand and attribute sets. *Marketing Letters, 23*, 585-601. [https://doi.org/10.1007/s11002-012-9163-8](https://doi.org/10.1007/s11002-012-9163-8)
