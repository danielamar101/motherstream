import { createFileRoute } from "@tanstack/react-router";
import { Container, Image, Text, VStack } from "@chakra-ui/react";

export const Route = createFileRoute("/about-motherstream")({
    component: AboutMotherstream,
  });

function AboutMotherstream() {
  return (
    <Container maxW="lg" centerContent>
      <VStack spacing={6} align="center" textAlign="center" mt={8}>
        <Image
          src="/assets/images/logo.png"
          alt="Motherstream Banner"
          maxW="2xs"
        //   borderRadius="md"
          alignSelf="center"
        />
        <Text fontSize="3xl" fontWeight="bold" color="#911c11">
          About Motherstream
        </Text>
        <Text fontSize="md" color="gray.700">
          Welcome to Motherstream, a platform dedicated to bringing high-quality streaming experiences to users worldwide.
        </Text>
        <Image
          src="/assets/images/motherstream-example.jpg"
          alt="Motherstream Example"
          maxW="full"
          borderRadius="md"
        />
        <Text fontSize="md" color="gray.700">
          Our mission is to provide seamless, reliable, and innovative streaming solutions, empowering creators and audiences alike.
        </Text>
      </VStack>
    </Container>
  );
}