import datetime as dt
import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import shape
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session
from tqdm.notebook import tqdm

from couchers.config import config
from couchers.db import session_scope
from couchers.models import (Cluster, ClusterRole, ClusterSubscription,
                             Discussion, EventOccurrence,
                             EventOccurrenceAttendee, EventOrganizer,
                             EventSubscription, Node, Page, PageType,
                             PageVersion, Thread, User)
from couchers.utils import create_coordinate, to_multi


def create_session():
    engine = create_engine(config["DATABASE_CONNECTION_STRING"])
    return Session(engine)


def get_table_columns(table):
    session = create_session()
    query = session.query(table).limit(0)
    df = pd.read_sql(query.statement, query.session.bind)
    result = list(df.columns)
    session.close()
    return result


def get_dataframe(table):
    session = create_session()
    query = session.query(table)
    result = pd.read_sql(query.statement, query.session.bind)
    session.close()
    return result


def update_community_description(node_id, description, overide_length_constraint=False):

    if len(description) > 500 and not overide_length_constraint:
        print(
            f"The description length is {len(description)}. The limit is 500 characters."
        )
        return

    with session_scope() as session:
        community = (
            session.query(Cluster).filter(Cluster.parent_node_id == node_id).one()
        )
        community.description = description
        name = community.name
        new_description = community.description
    print(f"The {name} community description has been updated to:\n{new_description}")


def delete_discussion(discussion_id):
    with session_scope() as session:
        discussion = (
            session.query(Discussion).filter(Discussion.id == discussion_id).one()
        )
        thread = discussion.thread
        comments = thread.comments

        for comment in comments:
            for reply in comment.replies:
                session.delete(reply)
            session.delete(comment)
        session.delete(thread)
        session.delete(discussion)

        session.commit()


def delete_event(event_id):

    with session_scope() as session:
        event_occurrence = (
            session.query(EventOccurrence).filter(EventOccurrence.id == event_id).one()
        )
        event = event_occurrence.event
        thread = event.thread

        for sub in event.subscribers:
            sub_entry = (
                session.query(EventSubscription)
                .filter(
                    (EventSubscription.event_id == event.id)
                    & (EventSubscription.user_id == sub.id)
                )
                .one()
            )
            session.delete(sub_entry)
        for org in event.organizers:
            org_entry = (
                session.query(EventOrganizer)
                .filter(
                    (EventOrganizer.event_id == event.id)
                    & (EventOrganizer.user_id == sub.id)
                )
                .one()
            )
            session.delete(org_entry)
        for att in event_occurrence.attendees:
            att_entry = (
                session.query(EventOccurrenceAttendee)
                .filter(
                    (EventOccurrenceAttendee.occurence_id == event_occurrence.id)
                    & (EventOccurrenceAttendee.user_id == sub.id)
                )
                .one()
            )
            session.delete(att_entry)

        session.delete(thread)
        session.delete(event_occurrence)
        session.delete(event)
        session.commit()


def new_admin(community_node_id, username):
    with session_scope() as session:
        user = session.query(User).filter(User.username == username).one()
        node = session.query(Node).filter(Node.id == community_node_id).one()
        cluster = node.official_cluster

        # if they are already a member change their role
        try:
            community_subscription = (
                session.query(ClusterSubscription)
                .filter(
                    (ClusterSubscription.user_id == user.id)
                    & (ClusterSubscription.cluster_id == cluster.id)
                )
                .one()
            )
            if community_subscription.role == ClusterRole.admin:
                print(f"{username} is ALREADY AN ADMIN of {cluster.name}")
                return
            else:
                community_subscription.role = ClusterRole.admin

        # else create new subscription
        except NoResultFound:
            cluster.cluster_subscriptions.append(
                ClusterSubscription(
                    user=user,
                    role=ClusterRole.admin,
                )
            )
        cluster_name = cluster.name
    print(f"{username} is now an admin of {cluster_name}")


def remove_admin(community_node_id, username):
    with session_scope() as session:
        user = session.query(User).filter(User.username == username).one()
        node = session.query(Node).filter(Node.id == community_node_id).one()
        cluster = node.official_cluster
        try:
            community_subscription = (
                session.query(ClusterSubscription)
                .filter(
                    (ClusterSubscription.user_id == user.id)
                    & (ClusterSubscription.cluster_id == cluster.id)
                )
                .one()
            )
        except NoResultFound:
            print(f"{username} is not an admin of the {cluster.name} community.")
            return

        if community_subscription.role == ClusterRole.member:
            print(f"{username} is not an admin of the {cluster.name} community.")
            return

        community_subscription.role = ClusterRole.member
        print(
            f"{username} has been removed as an admin from the {cluster.name} community."
        )


def create_community(
    session,
    geojson,
    lat,
    lng,
    name,
    cluster_description,
    main_page_title,
    main_page_content,
    admin_usernames,
    parent_node_id,
):
    admins = [
        session.query(User).filter(User.username == username).one()
        for username in admin_usernames
    ]
    geom = shape(json.loads(geojson)["features"][0]["geometry"])
    node = Node(
        geom=to_multi(geom.wkb),
        parent_node_id=parent_node_id,
    )
    session.add(node)
    cluster = Cluster(
        name=name,
        description=cluster_description,
        parent_node=node,
        is_official_cluster=True,
    )
    session.add(cluster)
    main_page = Page(
        parent_node=cluster.parent_node,
        creator_user=admins[0],
        owner_cluster=cluster,
        type=PageType.main_page,
        thread=Thread(),
    )
    session.add(main_page)
    page_version = PageVersion(
        page=main_page,
        editor_user=admins[0],
        title=main_page_title,
        content=main_page_content,
        geom=create_coordinate(lat, lng),
        address=name,
    )
    session.add(page_version)
    for admin in admins:
        cluster.cluster_subscriptions.append(
            ClusterSubscription(
                user=admin,
                role=ClusterRole.admin,
            )
        )
    session.flush()
    return node


def update_community_name(community_id: int, name: str):
    with session_scope() as session:
        node = session.query(Node).filter(Node.id == community_id).one()
        official_cluster = node.official_cluster
        old_name = official_cluster.name
        official_cluster.name = name
        official_cluster.main_page.versions[-1].title = name
    print(f"{old_name} community renamed to: {name}")


def get_incomplete_communities_df():
    with session_scope() as session:
        print("getting communities...")
        community_df = get_dataframe(Cluster).query("is_official_cluster == True")
        community_df["url"] = community_df.apply(
            lambda row: f"app.couchers.org/community/{row.parent_node_id}/{row.slugify_1}",
            axis=1,
        )
        result_df = community_df[
            ["id", "parent_node_id", "name", "url", "created"]
        ].copy()

        print("getting discussions...")
        discussion_df = get_dataframe(Discussion)

        result_df["has_discussions"] = result_df.id.apply(
            lambda x: _has_discussions(x, discussion_df)
        )

        tqdm.pandas(desc="getting properties for communities")
        (
            result_df["has_description_length"],
            result_df["has_main_page_length"],
            result_df["has_non_man_admin"],
        ) = zip(
            *result_df.parent_node_id.progress_apply(
                lambda x: _complete_community_properties(session, x)
            )
        )

        return result_df[
            ~(
                result_df.has_discussions
                & result_df.has_description_length
                & result_df.has_main_page_length
                & result_df.has_non_man_admin
            )
        ].sort_values("id")


def get_community_builder_df():
    user_columns = ["id", "name", "username", "email"]
    community_columns = ["id", "name", "slugify_1"]

    sub_df = get_dataframe(ClusterSubscription).rename(
        {"cluster_id": "community_id"}, axis=1
    )
    user_df = get_dataframe(User)[user_columns].rename({"id": "user_id"}, axis=1)
    community_df = get_dataframe(Cluster)[community_columns].rename(
        {"id": "community_id", "name": "community_name"}, axis=1
    )

    admin_df = sub_df[sub_df.role == ClusterRole.admin]

    CB_df = (
        admin_df.merge(right=user_df, on="user_id")
        .merge(right=community_df, on="community_id")
        .sort_values(["user_id", "community_id"])
        .reset_index(drop=True)
    )

    CB_df["profile_link"] = CB_df.username.apply(
        lambda x: f"https://app.couchers.org/user/{x}"
    )
    CB_df["community_link"] = CB_df.apply(
        lambda row: f"https://app.couchers.org/community/{row.community_id-1}/{row.slugify_1}",
        axis=1,
    )

    CB_df = CB_df.drop(["id", "user_id", "community_id", "role", "slugify_1"], axis=1)

    return (
        CB_df.groupby("username")
        .first()
        .reset_index()[
            [
                "name",
                "username",
                "email",
                "community_name",
                "profile_link",
                "community_link",
            ]
        ]
    )


def _has_discussions(community_id, discussion_df):
    num_discussions = discussion_df.query(
        f"owner_cluster_id == {str(community_id)}"
    ).shape[0]
    return num_discussions > 0


def _complete_community_properties(session, community_node_id):
    community = (
        session.query(Cluster).filter(Cluster.parent_node_id == community_node_id).one()
    )
    return (
        len(community.description) > 200,
        len(community.main_page.versions[-1].content) > 200,
        _has_non_man_admin(community),
    )


def _has_non_man_admin(community):
    admins = community.admins.all()
    for admin in admins:
        if admin.gender not in ["Man", "Male"]:
            return True
    return False


def users_per_day_plot(window_num_days=14, title=True):

    user_df = get_dataframe(User)
    df = (
        user_df[["joined"]]
        .sort_values("joined")
        .reset_index()
        .joined.dt.floor("d")
        .value_counts()
        .rename_axis("date")
        .sort_index()
        .reset_index()
    )

    df[f"last_{window_num_days}_avg"] = df.apply(
        lambda row: df[
            (df.date > row.date - dt.timedelta(days=window_num_days))
            & (df.date <= row.date)
        ].joined.sum()
        / window_num_days,
        axis=1,
    )

    plt.figure(figsize=(16, 9))

    orange = "#D97823"
    teal = "#1FA698"
    font = "Ubuntu"
    tickcolor = "#6a6a6a"
    background_color = "#dfe6e6"

    fig, ax = plt.subplots(figsize=(16, 9), facecolor=background_color)
    ax.set_facecolor(background_color)

    plt.ylim((0, df.joined.max() * 1.05))
    plt.xlim((df.date.min(), df.date.max()))

    plt.bar(df.date, df.joined, color=orange, width=0.5)
    plt.plot(
        df.date,
        df[f"last_{window_num_days}_avg"],
        color=teal,
        label=f"last_{window_num_days}_avg",
    )

    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_color(teal)
    ax.spines["left"].set_linewidth(2)
    ax.spines["bottom"].set_color(teal)
    ax.spines["bottom"].set_linewidth(2)

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    plt.yticks(fontsize=20, color=tickcolor, fontweight=0)
    plt.xticks(fontsize=20, color=tickcolor)
    ax.tick_params(colors=tickcolor, which="both")

    plt.legend()
    plt.grid(color=teal, linewidth=0.5, linestyle=(0, (5, 10)), axis="both")

    if title:
        plt.title(
            "New users per day",
            fontname=font,
            color=orange,
            fontsize=40,
            pad=50,
            fontweight=500,
        )


def user_growth_plot(frequency_sample_days=2, title=True):
    df = get_dataframe(User)
    df = (
        df[["joined"]]
        .sort_values("joined")
        .reset_index(drop=True)
        .reset_index(drop=False)
        .rename({"index": "cumulative_users"}, axis=1)
        .set_index("joined")
        .resample(f"{frequency_sample_days}d")
        .first()
        .fillna(method="ffill")
        .reset_index(drop=False)
    )

    orange = "#D97823"
    teal = "#1FA698"
    font = "Ubuntu"
    tickcolor = "#6a6a6a"
    background_color = "#dfe6e6"

    fig, ax = plt.subplots(figsize=(16, 9), facecolor=background_color)
    ax.set_facecolor(background_color)

    plt.ylim((0, df.cumulative_users.max() * 1.05))
    plt.xlim((df.joined.min(), df.joined.max()))

    ax.plot(df.joined, df.cumulative_users, color=orange, linewidth=4)
    ax.fill_between(df.joined, df.cumulative_users, 0, color=orange, alpha=0.4)

    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_color(teal)
    ax.spines["left"].set_linewidth(2)
    ax.spines["bottom"].set_color(teal)
    ax.spines["bottom"].set_linewidth(2)

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.yaxis.set_major_locator(plt.MaxNLocator(1))

    plt.yticks(fontsize=20, color=tickcolor, fontweight=0)
    plt.xticks(fontsize=20, color=tickcolor)
    ax.tick_params(colors=tickcolor, which="both")

    plt.grid(color=teal, linewidth=0.5, linestyle=(0, (5, 10)), axis="x")
    if title:
        plt.title(
            "Userbase growth on Couchers.org",
            fontname=font,
            color=orange,
            fontsize=40,
            pad=50,
            fontweight=500,
        )
    plt.savefig("userbase_growth.png", bbox_inches="tight")
    return plt.show()
