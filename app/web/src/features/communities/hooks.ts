import useUsers from "features/userQueries/useUsers";
import { Error as GrpcError } from "grpc-web";
import {
  Community,
  ListAdminsRes,
  ListCommunitiesRes,
  ListDiscussionsRes,
  ListEventsRes,
  ListGroupsRes,
  ListGuidesRes,
  ListMembersRes,
  ListNearbyUsersRes,
  ListPlacesRes,
} from "proto/communities_pb";
import { Discussion } from "proto/discussions_pb";
import { GetThreadRes } from "proto/threads_pb";
import {
  communityAdminsKey,
  communityDiscussionsKey,
  communityEventsKey,
  communityGroupsKey,
  communityGuidesKey,
  communityKey,
  communityMembersKey,
  communityNearbyUsersKey,
  communityPlacesKey,
  QueryType,
  subCommunitiesKey,
  threadKey,
} from "queryKeys";
import { useEffect } from "react";
import {
  useInfiniteQuery,
  UseInfiniteQueryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  UseQueryOptions,
} from "react-query";
import { useHistory, useParams } from "react-router-dom";
import { routeToCommunity } from "routes";
import { service } from "service";

export const useCommunity = (
  id: number | undefined,
  options?: Omit<
    UseQueryOptions<Community.AsObject | undefined, GrpcError>,
    "queryKey" | "queryFn" | "enabled"
  >
) => {
  const {
    communityId: communityIdFromUrl,
    communitySlug: communitySlugFromUrl,
  } = useParams<{
    communityId?: string;
    communitySlug?: string;
  }>();

  const communityId =
    id ?? (communityIdFromUrl ? +communityIdFromUrl : undefined);

  const queryResult = useQuery<Community.AsObject | undefined, GrpcError>(
    communityKey(communityId || -1),
    () =>
      communityId
        ? service.communities.getCommunity(communityId)
        : Promise.resolve(undefined),
    {
      ...options,
      enabled: !!communityId,
    }
  );

  const { data: { slug } = {} } = queryResult;

  const history = useHistory();

  useEffect(() => {
    // guarantee the most recent slug is used if the community was loaded from url params
    // if no slug was provided in the url, then also redirect to page with slug in url
    if (!id && slug && slug !== communitySlugFromUrl) {
      communityId && history.push(routeToCommunity(communityId, slug));
    }
  }, [communityId, slug, history, id, communitySlugFromUrl]);

  return {
    ...queryResult,
    queryCommunityId: communityId,
  };
};

//0 for communityId lists all communities
export const useListSubCommunities = (communityId?: number) =>
  useInfiniteQuery<ListCommunitiesRes.AsObject, GrpcError>(
    subCommunitiesKey(communityId || 0),
    ({ pageParam }) =>
      service.communities.listCommunities(communityId || 0, pageParam),
    {
      enabled: communityId !== undefined,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListGroups = (communityId?: number) =>
  useInfiniteQuery<ListGroupsRes.AsObject, GrpcError>(
    communityGroupsKey(communityId!),
    ({ pageParam }) => service.communities.listGroups(communityId!, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListPlaces = (communityId?: number) =>
  useInfiniteQuery<ListPlacesRes.AsObject, GrpcError>(
    communityPlacesKey(communityId!),
    ({ pageParam }) => service.communities.listPlaces(communityId!, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListGuides = (communityId?: number) =>
  useInfiniteQuery<ListGuidesRes.AsObject, GrpcError>(
    communityGuidesKey(communityId!),
    ({ pageParam }) => service.communities.listGuides(communityId!, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListDiscussions = (communityId: number) =>
  useInfiniteQuery<ListDiscussionsRes.AsObject, GrpcError>(
    communityDiscussionsKey(communityId),
    ({ pageParam }) =>
      service.communities.listDiscussions(communityId, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListAdmins = (communityId: number, type: QueryType) => {
  const query = useInfiniteQuery<ListAdminsRes.AsObject, GrpcError>(
    communityAdminsKey(communityId, type),
    ({ pageParam }) => service.communities.listAdmins(communityId, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );
  const adminIds = query.data?.pages.flatMap((page) => page.adminUserIdsList);
  const { data: adminUsers, isLoading: isAdminUsersLoading } = useUsers(
    adminIds ?? []
  );

  return {
    ...query,
    adminIds,
    adminUsers,
    isLoading: query.isLoading || isAdminUsersLoading,
  };
};

export const useListMembers = (communityId?: number) =>
  useInfiniteQuery<ListMembersRes.AsObject, GrpcError>(
    communityMembersKey(communityId!),
    ({ pageParam }) => service.communities.listMembers(communityId!, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

export const useListNearbyUsers = (communityId?: number) =>
  useInfiniteQuery<ListNearbyUsersRes.AsObject, GrpcError>(
    communityNearbyUsersKey(communityId!),
    ({ pageParam }) =>
      service.communities.listNearbyUsers(communityId!, pageParam),
    {
      enabled: !!communityId,
      getNextPageParam: (lastPage) =>
        lastPage.nextPageToken ? lastPage.nextPageToken : undefined,
    }
  );

interface UseListCommunityEventsInput {
  communityId: number;
  pageSize?: number;
  type: QueryType;
}

export function useListCommunityEvents({
  communityId,
  pageSize,
  type,
}: UseListCommunityEventsInput) {
  return useInfiniteQuery<ListEventsRes.AsObject, GrpcError>({
    queryKey: communityEventsKey(communityId, type),
    queryFn: ({ pageParam }) =>
      service.events.listCommunityEvents(communityId, pageParam, pageSize),
    getNextPageParam: (lastPage) => lastPage.nextPageToken || undefined,
  });
}

// Discussions
export interface CreateDiscussionInput {
  title: string;
  content: string;
  ownerCommunityId: number;
}

export const useNewDiscussionMutation = (onSuccess?: () => void) => {
  const queryClient = useQueryClient();
  return useMutation<Discussion.AsObject, GrpcError, CreateDiscussionInput>(
    ({ title, content, ownerCommunityId }) =>
      service.discussions.createDiscussion(title, content, ownerCommunityId),
    {
      onSuccess(_, { ownerCommunityId }) {
        onSuccess?.();
        queryClient.invalidateQueries(
          communityDiscussionsKey(ownerCommunityId)
        );
      },
    }
  );
};

export const useThread = (
  threadId: number,
  options?: Omit<
    UseInfiniteQueryOptions<GetThreadRes.AsObject, GrpcError>,
    "queryKey" | "queryFn" | "getNextPageParam"
  >
) =>
  useInfiniteQuery<GetThreadRes.AsObject, GrpcError>({
    queryKey: threadKey(threadId),
    queryFn: ({ pageParam }) => service.threads.getThread(threadId, pageParam),
    getNextPageParam: (lastPage) => lastPage.nextPageToken || undefined,
    ...options,
  });
