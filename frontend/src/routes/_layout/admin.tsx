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
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  useToast,
  VStack,
  HStack,
  Grid,
  GridItem,
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
    isError,
    error,
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
          ) : isError ? (
            <Tbody>
              <Tr>
                <Td colSpan={4}>
                  <Box color="red.500" textAlign="center" py={4}>
                    Error loading users: {error?.message || "Unknown error"}
                  </Box>
                </Td>
              </Tr>
            </Tbody>
          ) : users?.data && users.data.length > 0 ? (
            <Tbody>
              {users.data.map((user) => (
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
          ) : (
            <Tbody>
              <Tr>
                <Td colSpan={4}>
                  <Box textAlign="center" py={4} color="gray.500">
                    No users found. Total users: {users?.count || 0}
                  </Box>
                </Td>
              </Tr>
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
  const toast = useToast()
  const [selectedTime, setSelectedTime] = useState("5")
  const [resetTime, setResetTime] = useState(false)

  // OBS Source Controls
  const [obsSourceName, setObsSourceName] = useState("GMOTHERSTREAM")
  const [obsSceneName, setObsSceneName] = useState("MOTHERSTREAM")
  const [mediaSourceName, setMediaSourceName] = useState("GMOTHERSTREAM")
  const [zOffset, setZOffset] = useState("5")
  
  // Stream Switching Debug
  const [rtmpUrl, setRtmpUrl] = useState("rtmp://127.0.0.1:1935/live/test")
  
  // Stream Health Monitoring
  const [pollInterval, setPollInterval] = useState("1.0")
  
  // OBS Job Delay
  const [obsJobDelay, setObsJobDelay] = useState("2.0")
  
  // OBS Health Monitor Config
  const [healthCheckInterval, setHealthCheckInterval] = useState("30")
  const [maxReconnectAttempts, setMaxReconnectAttempts] = useState("5")
  const [reconnectDelay, setReconnectDelay] = useState("5")
  
  // Streaming Monitor Config
  const [streamingCheckInterval, setStreamingCheckInterval] = useState("15")
  const [maxAutoStartAttempts, setMaxAutoStartAttempts] = useState("3")
  const [autoStartDelay, setAutoStartDelay] = useState("10")

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8483"

  // GET /time-settings
  const {
    data: timeSettingsData,
    isLoading: isLoadingTimeSettings,
    error: timeSettingsError,
  } = useQuery({
    queryKey: ["time-settings"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/time-settings`)
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
      const res = await fetch(`${API_BASE_URL}/block-toggle`)
      if (!res.ok) throw new Error("Failed to fetch block toggle")
      return res.json()
    },
  })

  // Generic mutation helper with toast
  const createMutation = (url: string, method: string = "POST", successMessage: string) => {
    return useMutation({
      mutationFn: async (body?: any) => {
        const res = await fetch(url, {
          method,
          headers: body ? { "Content-Type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined,
        })
        if (!res.ok) {
          const errorData = await res.json().catch(() => null)
          throw new Error(errorData?.detail || "Request failed")
        }
        return res.json()
      },
      onSuccess: () => {
        toast({
          title: successMessage,
          status: "success",
          duration: 3000,
          isClosable: true,
        })
        queryClient.invalidateQueries({ queryKey: ["block-toggle"] })
        queryClient.invalidateQueries({ queryKey: ["time-settings"] })
      },
      onError: (error: any) => {
        toast({
          title: "Error",
          description: error.message,
          status: "error",
          duration: 5000,
          isClosable: true,
        })
      },
    })
  }

  // Mutations for all endpoints
  const toggleBlockMutation = createMutation(`${API_BASE_URL}/block-toggle`, "POST", "Block toggle updated")
  const updateTimerMutation = createMutation(`${API_BASE_URL}/update-timer/${selectedTime}?reset_time=${resetTime}`, "POST", "Timer updated")
  
  // OBS Source Controls
  const toggleObsSourceMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/obs/toggle-source?source_name=${obsSourceName}&scene_name=${obsSceneName}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to toggle OBS source")
      return res.json()
    },
    onSuccess: () => toast({ title: "OBS source toggled", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  const restartMediaSourceMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/obs/restart-media-source?input_name=${mediaSourceName}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to restart media source")
      return res.json()
    },
    onSuccess: () => toast({ title: "Media source restarted", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  const setSourceZOffsetMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/debug/set-source-z-offset?z_offset=${zOffset}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to set z-offset")
      return res.json()
    },
    onSuccess: () => toast({ title: "Z-offset updated", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  // Stream Switching Debug
  const testJobToggleMutation = createMutation(`${API_BASE_URL}/debug/test-job-toggle`, "POST", "Test job added to queue")
  const simulateStreamSwitchMutation = createMutation(`${API_BASE_URL}/debug/simulate-stream-switch`, "POST", "Stream switch simulated")
  
  const testDynamicSourceSwitchMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/debug/test-dynamic-source-switch?rtmp_url=${encodeURIComponent(rtmpUrl)}&scene_name=${obsSceneName}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to test dynamic source switch")
      return res.json()
    },
    onSuccess: () => toast({ title: "Dynamic source switch triggered", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  // Stream Health Monitoring
  const configureStreamHealthMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/stream-health/configure?poll_interval=${pollInterval}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to configure stream health monitoring")
      return res.json()
    },
    onSuccess: () => toast({ title: "Stream health monitoring configured", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  const stopStreamHealthMutation = createMutation(`${API_BASE_URL}/stream-health/stop`, "POST", "Stream health monitoring stopped")
  
  // OBS Connection Management
  const forceReconnectMutation = createMutation(`${API_BASE_URL}/obs/force-reconnect`, "POST", "OBS reconnection triggered")
  
  const updateObsJobDelayMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/debug/update-obs-job-delay?delay_seconds=${obsJobDelay}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to update OBS job delay")
      return res.json()
    },
    onSuccess: () => toast({ title: "OBS job delay updated", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  const updateObsHealthMonitorMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/debug/update-obs-health-monitor-config?health_check_interval=${healthCheckInterval}&max_reconnect_attempts=${maxReconnectAttempts}&reconnect_delay=${reconnectDelay}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to update OBS health monitor config")
      return res.json()
    },
    onSuccess: () => toast({ title: "OBS health monitor config updated", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  // OBS Streaming Controls
  const enableStreamingMonitorMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const res = await fetch(`${API_BASE_URL}/obs/enable-streaming-monitor?enabled=${enabled}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to toggle streaming monitor")
      return res.json()
    },
    onSuccess: () => toast({ title: "Streaming monitor toggled", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })
  
  const forceStartStreamingMutation = createMutation(`${API_BASE_URL}/obs/force-start-streaming`, "POST", "OBS streaming force-started")
  const checkStreamingNowMutation = createMutation(`${API_BASE_URL}/obs/check-streaming-now`, "GET", "Streaming status checked")
  
  const updateStreamingMonitorConfigMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE_URL}/debug/update-streaming-monitor-config?streaming_check_interval=${streamingCheckInterval}&max_auto_start_attempts=${maxAutoStartAttempts}&auto_start_delay=${autoStartDelay}`, { method: "POST" })
      if (!res.ok) throw new Error("Failed to update streaming monitor config")
      return res.json()
    },
    onSuccess: () => toast({ title: "Streaming monitor config updated", status: "success", duration: 3000 }),
    onError: (error: any) => toast({ title: "Error", description: error.message, status: "error", duration: 5000 }),
  })

  return (
    <VStack spacing={6} align="stretch" mt={8}>
      {/* Timer & Queue Settings */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          Timer & Queue Settings
        </Heading>

        <VStack spacing={4} align="stretch">
          {/* Time Settings Display */}
          <Box>
            <Heading size="sm" mb={2}>Current Time Settings</Heading>
            {isLoadingTimeSettings ? (
              <SkeletonText noOfLines={2} />
            ) : timeSettingsError ? (
              <Box color="red.500">Error loading time settings</Box>
            ) : (
              <Box fontSize="sm">
                <Box>Swap Interval: {timeSettingsData.swap_interval} min</Box>
                <Box>Remaining Time: {timeSettingsData.remaining_time} sec</Box>
              </Box>
            )}
          </Box>

          {/* Block Toggle */}
          <Box>
            <Heading size="sm" mb={2}>Block Last Streamer</Heading>
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
                {blockToggleData?.last_stream_key && ` (${blockToggleData.last_stream_key})`}
              </Checkbox>
            )}
          </Box>

          {/* Update Timer */}
          <Box>
            <Heading size="sm" mb={2}>Update Timer</Heading>
            <HStack>
              <Select
                value={selectedTime}
                onChange={(e) => setSelectedTime(e.target.value)}
                width="120px"
              >
                <option value="1">1 min</option>
                <option value="5">5 min</option>
                <option value="10">10 min</option>
                <option value="15">15 min</option>
                <option value="30">30 min</option>
                <option value="60">60 min</option>
              </Select>
              <Checkbox
                isChecked={resetTime}
                onChange={(e) => setResetTime(e.target.checked)}
              >
                Reset Time?
              </Checkbox>
              <Button
                onClick={() => updateTimerMutation.mutate({ time: selectedTime, resetTime })}
                isLoading={updateTimerMutation.isPending}
                colorScheme="blue"
              >
                Update Timer
              </Button>
            </HStack>
          </Box>
        </VStack>
      </Box>

      {/* OBS Source Controls */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          OBS Source Controls
        </Heading>
        
        <VStack spacing={4} align="stretch">
          <Box>
            <Heading size="sm" mb={2}>Toggle OBS Source</Heading>
            <HStack>
              <Input
                placeholder="Source Name"
                value={obsSourceName}
                onChange={(e) => setObsSourceName(e.target.value)}
                width="200px"
              />
              <Input
                placeholder="Scene Name"
                value={obsSceneName}
                onChange={(e) => setObsSceneName(e.target.value)}
                width="200px"
              />
              <Button
                onClick={() => toggleObsSourceMutation.mutate()}
                isLoading={toggleObsSourceMutation.isPending}
                colorScheme="purple"
              >
                Toggle Source
              </Button>
            </HStack>
          </Box>

          <Box>
            <Heading size="sm" mb={2}>Restart Media Source</Heading>
            <HStack>
              <Input
                placeholder="Media Source Name"
                value={mediaSourceName}
                onChange={(e) => setMediaSourceName(e.target.value)}
                width="200px"
              />
              <Button
                onClick={() => restartMediaSourceMutation.mutate()}
                isLoading={restartMediaSourceMutation.isPending}
                colorScheme="purple"
              >
                Restart Media
              </Button>
            </HStack>
          </Box>

          <Box>
            <Heading size="sm" mb={2}>Set Source Z-Offset</Heading>
            <HStack>
              <NumberInput
                value={zOffset}
                onChange={(value) => setZOffset(value)}
                min={0}
                max={50}
                width="120px"
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <Button
                onClick={() => setSourceZOffsetMutation.mutate()}
                isLoading={setSourceZOffsetMutation.isPending}
                colorScheme="purple"
              >
                Set Z-Offset
              </Button>
            </HStack>
          </Box>
        </VStack>
      </Box>

      {/* Stream Switching Debug */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          Stream Switching Debug
        </Heading>
        
        <VStack spacing={4} align="stretch">
          <HStack>
            <Button
              onClick={() => testJobToggleMutation.mutate()}
              isLoading={testJobToggleMutation.isPending}
              colorScheme="orange"
            >
              Test Job Toggle
            </Button>
            <Button
              onClick={() => simulateStreamSwitchMutation.mutate()}
              isLoading={simulateStreamSwitchMutation.isPending}
              colorScheme="orange"
            >
              Simulate Stream Switch
            </Button>
          </HStack>

          <Box>
            <Heading size="sm" mb={2}>Test Dynamic Source Switch</Heading>
            <HStack>
              <Input
                placeholder="RTMP URL"
                value={rtmpUrl}
                onChange={(e) => setRtmpUrl(e.target.value)}
                flex="1"
              />
              <Button
                onClick={() => testDynamicSourceSwitchMutation.mutate()}
                isLoading={testDynamicSourceSwitchMutation.isPending}
                colorScheme="orange"
              >
                Test Switch
              </Button>
            </HStack>
          </Box>
        </VStack>
      </Box>

      {/* Stream Health Monitoring */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          Stream Health Monitoring
        </Heading>
        
        <VStack spacing={4} align="stretch">
          <Box>
            <Heading size="sm" mb={2}>Configure Monitoring</Heading>
            <HStack>
              <NumberInput
                value={pollInterval}
                onChange={(value) => setPollInterval(value)}
                min={0.1}
                max={10.0}
                step={0.1}
                width="120px"
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <Box fontSize="sm">seconds</Box>
              <Button
                onClick={() => configureStreamHealthMutation.mutate()}
                isLoading={configureStreamHealthMutation.isPending}
                colorScheme="teal"
              >
                Configure
              </Button>
            </HStack>
          </Box>

          <Button
            onClick={() => stopStreamHealthMutation.mutate()}
            isLoading={stopStreamHealthMutation.isPending}
            colorScheme="red"
            width="fit-content"
          >
            Stop Monitoring
          </Button>
        </VStack>
      </Box>

      {/* OBS Connection Management */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          OBS Connection Management
        </Heading>
        
        <VStack spacing={4} align="stretch">
          <Button
            onClick={() => forceReconnectMutation.mutate()}
            isLoading={forceReconnectMutation.isPending}
            colorScheme="cyan"
            width="fit-content"
          >
            Force OBS Reconnect
          </Button>

          <Box>
            <Heading size="sm" mb={2}>OBS Job Delay</Heading>
            <HStack>
              <NumberInput
                value={obsJobDelay}
                onChange={(value) => setObsJobDelay(value)}
                min={0.5}
                max={10.0}
                step={0.1}
                width="120px"
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <Box fontSize="sm">seconds</Box>
              <Button
                onClick={() => updateObsJobDelayMutation.mutate()}
                isLoading={updateObsJobDelayMutation.isPending}
                colorScheme="cyan"
              >
                Update Delay
              </Button>
            </HStack>
          </Box>

          <Box>
            <Heading size="sm" mb={2}>OBS Health Monitor Config</Heading>
            <Grid templateColumns="repeat(2, 1fr)" gap={4}>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Health Check Interval (s)</FormLabel>
                  <NumberInput
                    value={healthCheckInterval}
                    onChange={(value) => setHealthCheckInterval(value)}
                    min={10}
                    max={300}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Max Reconnect Attempts</FormLabel>
                  <NumberInput
                    value={maxReconnectAttempts}
                    onChange={(value) => setMaxReconnectAttempts(value)}
                    min={1}
                    max={20}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Reconnect Delay (s)</FormLabel>
                  <NumberInput
                    value={reconnectDelay}
                    onChange={(value) => setReconnectDelay(value)}
                    min={1}
                    max={60}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
            </Grid>
            <Button
              onClick={() => updateObsHealthMonitorMutation.mutate()}
              isLoading={updateObsHealthMonitorMutation.isPending}
              colorScheme="cyan"
              mt={2}
            >
              Update Health Monitor Config
            </Button>
          </Box>
        </VStack>
      </Box>

      {/* OBS Streaming Controls */}
      <Box border="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Heading size="md" mb={4}>
          OBS Streaming Controls
        </Heading>
        
        <VStack spacing={4} align="stretch">
          <HStack>
            <Button
              onClick={() => enableStreamingMonitorMutation.mutate(true)}
              isLoading={enableStreamingMonitorMutation.isPending}
              colorScheme="green"
            >
              Enable Monitor
            </Button>
            <Button
              onClick={() => enableStreamingMonitorMutation.mutate(false)}
              isLoading={enableStreamingMonitorMutation.isPending}
              colorScheme="red"
            >
              Disable Monitor
            </Button>
            <Button
              onClick={() => forceStartStreamingMutation.mutate()}
              isLoading={forceStartStreamingMutation.isPending}
              colorScheme="green"
            >
              Force Start Streaming
            </Button>
            <Button
              onClick={() => checkStreamingNowMutation.mutate()}
              isLoading={checkStreamingNowMutation.isPending}
              colorScheme="blue"
            >
              Check Status Now
            </Button>
          </HStack>

          <Box>
            <Heading size="sm" mb={2}>Streaming Monitor Config</Heading>
            <Grid templateColumns="repeat(2, 1fr)" gap={4}>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Check Interval (s)</FormLabel>
                  <NumberInput
                    value={streamingCheckInterval}
                    onChange={(value) => setStreamingCheckInterval(value)}
                    min={5}
                    max={120}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Max Auto-Start Attempts</FormLabel>
                  <NumberInput
                    value={maxAutoStartAttempts}
                    onChange={(value) => setMaxAutoStartAttempts(value)}
                    min={1}
                    max={10}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
              <GridItem>
                <FormControl>
                  <FormLabel fontSize="sm">Auto-Start Delay (s)</FormLabel>
                  <NumberInput
                    value={autoStartDelay}
                    onChange={(value) => setAutoStartDelay(value)}
                    min={5}
                    max={60}
                  >
                    <NumberInputField />
                  </NumberInput>
                </FormControl>
              </GridItem>
            </Grid>
            <Button
              onClick={() => updateStreamingMonitorConfigMutation.mutate()}
              isLoading={updateStreamingMonitorConfigMutation.isPending}
              colorScheme="green"
              mt={2}
            >
              Update Streaming Config
            </Button>
          </Box>
        </VStack>
      </Box>
    </VStack>
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
