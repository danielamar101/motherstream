import {
  Box,
  Container,
  Flex,
  Heading,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  Checkbox,
  Select,
  Button,
  FormControl,
  FormLabel,
} from "@chakra-ui/react"
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { z } from "zod"

import { type UserPublic, UsersService } from "../../client"
import AddUser from "../../components/Admin/AddUser"
import ActionsMenu from "../../components/Common/ActionsMenu"
import Navbar from "../../components/Common/Navbar"
import { PaginationFooter } from "../../components/Common/PaginationFooter.tsx"

const usersSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  validateSearch: (search) => usersSearchSchema.parse(search),
})

const PER_PAGE = 5

function getUsersQueryOptions({ page }: { page: number }) {
  return {
    queryKey: ["users", { page }],
    queryFn: () =>
      UsersService.readUsers({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
  }
}

function UsersTable() {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) })

  const {
    data: users,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getUsersQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const hasNextPage = !isPlaceholderData && users?.data.length === PER_PAGE
  const hasPreviousPage = page > 1

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getUsersQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  return (
    <>
      <TableContainer>
        <Table size={{ base: "sm", md: "md" }}>
          <Thead>
            <Tr>
              <Th width="50%">Email</Th>
              <Th width="10%">Role</Th>
              <Th width="10%">Status</Th>
              <Th width="10%">Actions</Th>
            </Tr>
          </Thead>
          {isPending ? (
            <Tbody>
              <Tr>
                {new Array(4).fill(null).map((_, index) => (
                  <Td key={index}>
                    <SkeletonText noOfLines={1} paddingBlock="16px" />
                  </Td>
                ))}
              </Tr>
            </Tbody>
          ) : (
            <Tbody>
              {users?.data.map((user) => (
                <Tr key={user.id}>
                  <Td isTruncated maxWidth="150px">
                    {user.email}
                  </Td>
                  <Td>{user.is_superuser ? "Superuser" : "User"}</Td>
                  <Td>
                    <Flex gap={2}>
                      <Box
                        w="2"
                        h="2"
                        borderRadius="50%"
                        bg={user.is_active ? "ui.success" : "ui.danger"}
                        alignSelf="center"
                      />
                      {user.is_active ? "Active" : "Inactive"}
                    </Flex>
                  </Td>
                  <Td>
                    <ActionsMenu
                      type="User"
                      value={user}
                      disabled={currentUser?.id === user.id}
                    />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          )}
        </Table>
      </TableContainer>
      <PaginationFooter
        onChangePage={setPage}
        page={page}
        hasNextPage={hasNextPage}
        hasPreviousPage={hasPreviousPage}
      />
    </>
  )
}

function StreamSettingsPanel() {
  const queryClient = useQueryClient()
  const [selectedTime, setSelectedTime] = useState("5")
  const [resetTime, setResetTime] = useState(false)

  // GET /time-settings
  const {
    data: timeSettingsData,
    isLoading: isLoadingTimeSettings,
    error: timeSettingsError,
  } = useQuery({
    queryKey: ["time-settings"],
    queryFn: async () => {
      const res = await fetch("/time-settings")
      if (!res.ok) throw new Error("Failed to fetch time settings")
      return res.json()
    },
  })

  // GET /block-toggle
  const {
    data: blockToggleData,
    isLoading: isLoadingBlockToggle,
    error: blockToggleError,
  } = useQuery({
    queryKey: ["block-toggle"],
    queryFn: async () => {
      const res = await fetch("/block-toggle")
      if (!res.ok) throw new Error("Failed to fetch block toggle")
      return res.json()
    },
  })

  // POST /block-toggle mutation (toggles blocking)
  const toggleBlockMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/block-toggle", {
        method: "POST",
      })
      if (!res.ok) throw new Error("Failed to toggle block")
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["block-toggle"] })
    },
  })

  // POST /update-timer/{time}?reset_time=<true|false> mutation
  const updateTimerMutation = useMutation({
    mutationFn: async ({ time, resetTime }: { time: string; resetTime: boolean }) => {
      const res = await fetch(`/update-timer/${time}?reset_time=${resetTime}`, {
        method: "POST",
      })
      if (!res.ok) throw new Error("Failed to update timer")
      return res.json()
    },
  })

  return (
    <Box border="1px" borderColor="gray.200" borderRadius="md" p={4} mt={8}>
      <Heading size="md" mb={4}>
        Stream Settings
      </Heading>

      {/* Time Settings */}
      <Box mb={4}>
        <Heading size="sm" mb={2}>
          Time Settings
        </Heading>
        {isLoadingTimeSettings ? (
          <SkeletonText noOfLines={2} />
        ) : timeSettingsError ? (
          <Box color="red.500">Error loading time settings</Box>
        ) : (
          <Box>
            <Box>Swap Interval: {timeSettingsData.swap_interval}</Box>
            <Box>Remaining Time: {timeSettingsData.remaining_time}</Box>
          </Box>
        )}
      </Box>

      {/* Block Toggle */}
      <Box mb={4}>
        <Heading size="sm" mb={2}>
          Block Toggle
        </Heading>
        {isLoadingBlockToggle ? (
          <SkeletonText noOfLines={1} />
        ) : blockToggleError ? (
          <Box color="red.500">Error loading block toggle</Box>
        ) : (
          <Checkbox
            isChecked={blockToggleData?.is_blocked}
            onChange={() => toggleBlockMutation.mutate()}
          >
            {blockToggleData?.is_blocked ? "Blocked" : "Not Blocked"}
          </Checkbox>
        )}
      </Box>

      {/* Update Timer */}
      <Box border="1px" borderColor="gray.100" p={4} borderRadius="md">
        <Heading size="sm" mb={2}>
          Update Timer
        </Heading>
        <Flex align="center" gap={4}>
          <FormControl>
            <FormLabel htmlFor="timer-select" mb={1}>
              Timer (minutes)
            </FormLabel>
            <Select
              id="timer-select"
              value={selectedTime}
              onChange={(e) => setSelectedTime(e.target.value)}
              width="100px"
            >
              <option value="1">1</option>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="15">15</option>
              <option value="30">30</option>
              <option value="60">60</option>
            </Select>
          </FormControl>
          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="reset-toggle" mb="0">
              Reset Time?
            </FormLabel>
            <Checkbox
              id="reset-toggle"
              isChecked={resetTime}
              onChange={(e) => setResetTime(e.target.checked)}
            />
          </FormControl>
          <Button
            onClick={() =>
              updateTimerMutation.mutate({ time: selectedTime, resetTime })
            }
            isLoading={updateTimerMutation.isLoading}
          >
            Update Timer
          </Button>
        </Flex>
        {updateTimerMutation.isError && (
          <Box color="red.500" mt={2}>
            Error updating timer
          </Box>
        )}
        {updateTimerMutation.isSuccess && (
          <Box color="green.500" mt={2}>
            Timer updated successfully!
          </Box>
        )}
      </Box>
    </Box>
  )
}

function Admin() {
  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} pt={12}>
        Users Management
      </Heading>

      <Navbar type={"User"} addModalAs={AddUser} />
      <UsersTable />
      <StreamSettingsPanel />
    </Container>
  )
}

export default Admin
