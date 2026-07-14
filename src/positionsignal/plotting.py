"""Accessible Plotly views for PositionSignal results."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .mapping import BootstrapResult, MapResult, nearest_competitors


INK = "#17322E"
TEAL = "#173C3A"
CORAL = "#D95B40"
MINT = "#83D2B4"
GOLD = "#F2C66D"
PAPER = "#F8F5ED"
MUTED = "#59716C"
GRID = "rgba(23,50,46,.12)"


def _base_layout(figure: go.Figure, height: int = 520) -> go.Figure:
    figure.update_layout(
        font={"family": "Arial, sans-serif", "color": INK},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,.54)",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=height,
        legend_title_text="",
        hoverlabel={"bgcolor": PAPER, "font_color": INK},
    )
    return figure


def _brand_text_positions(coordinates) -> dict[str, str]:
    """Place each label away from its nearest neighbour to reduce collisions."""
    points = coordinates[["pc1", "pc2"]].to_numpy(dtype=float)
    labels = coordinates["brand"].astype(str).tolist()
    if len(points) < 2:
        return {labels[0]: "top center"} if labels else {}

    positions: dict[str, str] = {}
    for index, (brand, point) in enumerate(zip(labels, points, strict=True)):
        distances = np.linalg.norm(points - point, axis=1)
        distances[index] = np.inf
        away = point - points[int(np.argmin(distances))]
        horizontal, vertical = float(away[0]), float(away[1])
        if abs(horizontal) > 1.6 * abs(vertical):
            position = "middle right" if horizontal >= 0 else "middle left"
        elif abs(vertical) > 1.6 * abs(horizontal):
            position = "top center" if vertical >= 0 else "bottom center"
        else:
            vertical_word = "top" if vertical >= 0 else "bottom"
            horizontal_word = "right" if horizontal >= 0 else "left"
            position = f"{vertical_word} {horizontal_word}"
        positions[brand] = position
    return positions


def perceptual_map_figure(
    result: MapResult,
    target_brand: str | None = None,
    show_attribute_vectors: bool = True,
    vector_limit: int = 12,
    bootstrap: BootstrapResult | None = None,
) -> go.Figure:
    """Draw directly labelled brand scores and row-metric biplot arrows."""
    coords = result.brand_coordinates.copy()
    coords[["pc1", "pc2"]] = coords[["pc1", "pc2"]] / result.biplot_scale
    range_x = coords["pc1"].astype(float).tolist()
    range_y = coords["pc2"].astype(float).tolist()
    target_brand = target_brand if target_brand in coords["brand"].tolist() else None
    text_positions = _brand_text_positions(coords)
    if target_brand is not None and text_positions[target_brand].startswith("middle"):
        target_row = coords.loc[coords["brand"] == target_brand].iloc[0]
        side = text_positions[target_brand].split()[-1]
        vertical = "top" if float(target_row["pc2"]) >= 0 else "bottom"
        text_positions[target_brand] = f"{vertical} {side}"
    coordinate_scale = max(
        1.0,
        float(coords[["pc1", "pc2"]].abs().to_numpy().max()),
    )
    for _, row in coords.iterrows():
        brand = str(row["brand"])
        position = text_positions[brand]
        label_width = 0.035 * len(brand) * coordinate_scale
        x, y = float(row["pc1"]), float(row["pc2"])
        if "left" in position:
            range_x.append(x - label_width)
        elif "right" in position:
            range_x.append(x + label_width)
        else:
            range_x.extend([x - label_width / 2, x + label_width / 2])
        if "top" in position:
            range_y.append(y + 0.12 * coordinate_scale)
        elif "bottom" in position:
            range_y.append(y - 0.12 * coordinate_scale)
    figure = go.Figure()

    if bootstrap is not None and not bootstrap.ellipses.empty:
        for brand, ellipse in bootstrap.ellipses.groupby("brand", sort=False):
            focus = brand == target_brand
            shown = ellipse.copy()
            shown[["pc1", "pc2"]] = shown[["pc1", "pc2"]] / result.biplot_scale
            range_x.extend(shown["pc1"].astype(float).tolist())
            range_y.extend(shown["pc2"].astype(float).tolist())
            figure.add_trace(
                go.Scatter(
                    x=shown["pc1"], y=shown["pc2"], mode="lines",
                    line={"color": CORAL if focus else TEAL, "width": 1.8 if focus else 1.0},
                    opacity=0.35 if focus else 0.18,
                    hoverinfo="skip", showlegend=False,
                )
            )

    competitors = coords if target_brand is None else coords[coords["brand"] != target_brand]
    if not competitors.empty:
        figure.add_trace(
            go.Scatter(
                x=competitors["pc1"], y=competitors["pc2"], mode="markers+text",
                text=competitors["brand"],
                textposition=[text_positions[str(brand)] for brand in competitors["brand"]],
                cliponaxis=False,
                marker={"size": 14, "color": TEAL, "line": {"color": PAPER, "width": 2}, "symbol": "circle"},
                textfont={"size": 12, "color": INK}, name="Competitors",
                customdata=np.c_[competitors["brand"], competitors["map_quality"]],
                hovertemplate="<b>%{customdata[0]}</b><br>PC1 %{x:.2f}<br>PC2 %{y:.2f}<br>2-D representation %{customdata[1]:.0%}<extra></extra>",
            )
        )
    if target_brand is not None:
        target = coords[coords["brand"] == target_brand]
        figure.add_trace(
            go.Scatter(
                x=target["pc1"], y=target["pc2"], mode="markers+text",
                text=target["brand"],
                textposition=[text_positions[str(brand)] for brand in target["brand"]],
                cliponaxis=False,
                marker={"size": 19, "color": CORAL, "line": {"color": PAPER, "width": 3}, "symbol": "diamond"},
                textfont={"size": 13, "color": CORAL}, name="Focus brand",
                customdata=np.c_[target["brand"], target["map_quality"]],
                hovertemplate="<b>%{customdata[0]}</b><br>PC1 %{x:.2f}<br>PC2 %{y:.2f}<br>2-D representation %{customdata[1]:.0%}<extra></extra>",
            )
        )

    if show_attribute_vectors and vector_limit > 0:
        attributes = result.attribute_coordinates.nlargest(vector_limit, "map_quality").copy()
        for _, row in attributes.iterrows():
            x = float(row["pc1_coefficient"] * result.biplot_scale)
            y = float(row["pc2_coefficient"] * result.biplot_scale)
            range_x.append(x * 1.14)
            range_y.append(y * 1.14)
            figure.add_annotation(
                x=x, y=y, ax=0, ay=0, axref="x", ayref="y", text="",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.35, arrowcolor=CORAL,
            )
            figure.add_annotation(
                x=x * 1.09, y=y * 1.09, text=str(row["attribute"]), showarrow=False,
                font={"size": 10, "color": "#9B3E2B"}, bgcolor="rgba(248,245,237,.82)", borderpad=2,
            )

    limit = max([abs(value) for value in [*range_x, *range_y] if np.isfinite(value)] or [1.0]) * 1.10
    variance = result.explained_variance["explained_ratio"].tolist()
    figure.update_xaxes(
        title=f"PC1 · {variance[0]:.1%} of profile variance", zeroline=True, zerolinecolor=MUTED,
        gridcolor=GRID, scaleanchor="y", scaleratio=1, range=[-limit, limit], constrain="domain",
    )
    figure.update_yaxes(
        title=f"PC2 · {variance[1]:.1%} of profile variance", zeroline=True, zerolinecolor=MUTED,
        gridcolor=GRID, range=[-limit, limit], constrain="domain",
    )
    figure.update_layout(
        title={"text": "Brand positioning map", "font": {"size": 20}},
        hovermode="closest",
        legend={"orientation": "h", "x": 0, "xanchor": "left", "y": 1.01, "yanchor": "bottom"},
    )
    _base_layout(figure, height=550)
    figure.update_layout(margin={"l": 20, "r": 20, "t": 105, "b": 20})
    return figure


def correlation_circle_figure(result: MapResult) -> go.Figure:
    """Show attribute correlations with PC1/PC2 on their natural unit circle."""
    attributes = result.attribute_coordinates
    figure = go.Figure()
    theta = np.linspace(0, 2 * np.pi, 240)
    figure.add_trace(
        go.Scatter(
            x=np.cos(theta), y=np.sin(theta), mode="lines",
            line={"color": GRID, "dash": "dot"}, hoverinfo="skip", showlegend=False,
        )
    )
    for _, row in attributes.iterrows():
        quality = float(row["map_quality"])
        color = CORAL if quality >= 0.50 else MUTED
        figure.add_annotation(
            x=float(row["pc1_correlation"]), y=float(row["pc2_correlation"]),
            ax=0, ay=0, axref="x", ayref="y", text="", showarrow=True,
            arrowhead=2, arrowwidth=1.4 if quality >= 0.50 else 0.9, arrowcolor=color,
            opacity=1.0 if quality >= 0.50 else 0.52,
        )
        figure.add_annotation(
            x=float(row["pc1_correlation"]) * 1.05, y=float(row["pc2_correlation"]) * 1.05,
            text=str(row["attribute"]), showarrow=False,
            opacity=1.0 if quality >= 0.50 else 0.52, font={"size": 10, "color": color},
            bgcolor="rgba(248,245,237,.80)", borderpad=2,
        )
    figure.update_xaxes(
        range=[-1.12, 1.12], title="Correlation with PC1", zeroline=True,
        gridcolor=GRID, scaleanchor="y", scaleratio=1,
    )
    figure.update_yaxes(range=[-1.12, 1.12], title="Correlation with PC2", zeroline=True, gridcolor=GRID)
    figure.update_layout(title="Attribute correlation circle", showlegend=False)
    return _base_layout(figure, height=520)


def scree_figure(result: MapResult) -> go.Figure:
    data = result.explained_variance.copy()
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=data["component"], y=data["explained_ratio"], name="Each component",
            marker_color=[CORAL if index < 2 else TEAL for index in range(len(data))],
            hovertemplate="%{x}<br>Explained variance %{y:.1%}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["component"], y=data["cumulative_ratio"], name="Cumulative",
            mode="lines+markers", line={"color": GOLD, "width": 3}, marker={"size": 8},
            hovertemplate="Through %{x}<br>Cumulative %{y:.1%}<extra></extra>",
        )
    )
    figure.update_yaxes(tickformat=".0%", range=[0, 1.05], gridcolor=GRID, title="Share of profile variance")
    figure.update_xaxes(title="Component")
    figure.update_layout(title="How much structure each dimension retains", barmode="group")
    return _base_layout(figure, height=420)


def profile_heatmap_figure(result: MapResult) -> go.Figure:
    matrix = result.analysis_matrix
    figure = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(), x=matrix.columns.astype(str), y=matrix.index.astype(str),
            colorscale=[[0, CORAL], [0.5, PAPER], [1, TEAL]], zmid=0,
            colorbar={"title": "Relative<br>rating"},
            hovertemplate="Brand %{y}<br>Attribute %{x}<br>Centered/scaled value %{z:.2f}<extra></extra>",
        )
    )
    figure.update_layout(title="The profile matrix behind the map")
    figure.update_xaxes(tickangle=-28)
    return _base_layout(figure, height=max(360, 40 * len(matrix) + 150))


def competitor_distance_figure(result: MapResult, target_brand: str) -> go.Figure:
    distances = nearest_competitors(result, target_brand).sort_values("full_distance", ascending=True)
    figure = go.Figure(
        go.Bar(
            x=distances["full_distance"], y=distances["competitor"], orientation="h",
            marker_color=[CORAL if index == 0 else TEAL for index in range(len(distances))],
            customdata=distances[["map_distance", "distance_retained"]],
            hovertemplate="%{y}<br>Full-profile distance %{x:.2f}<br>2-D distance %{customdata[0]:.2f}<br>Distance retained %{customdata[1]:.0%}<extra></extra>",
        )
    )
    figure.update_yaxes(autorange="reversed", title="")
    figure.update_xaxes(title="Full-profile distance", gridcolor=GRID)
    figure.update_layout(title=f"Closest profiles to {target_brand}")
    return _base_layout(figure, height=max(350, 42 * len(distances) + 140))
