import { Box, Container, Link, Text } from "@chakra-ui/react"
import { Link as RouterLink, createFileRoute } from "@tanstack/react-router"

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
          <Text>
            What do I do with this?{" "}
            <Link as={RouterLink} to="/about-motherstream" color="blue.500" textDecoration="underline">
              Learn more about Motherstream
            </Link>
          </Text>
        </Box>

      </Container>
    </>
  )
}
