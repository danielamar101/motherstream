import { Box, Container, Text } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"

import useAuth from "../../hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <>
      <Container maxW="full">
        <Box pt={12} m={4}>
          <Text fontSize="2xl">
            Hi, {currentUser?.dj_name || currentUser?.email} 👋🏼
          </Text>
        </Box>
        <Box pt={12} m={2}>
          <Text fontSize="2xl">Welcome back. Your stream key is: {currentUser?.stream_key}</Text> 
          <Text>What do i do with this? (insert link later)</Text>
        </Box>

      </Container>
    </>
  )
}
