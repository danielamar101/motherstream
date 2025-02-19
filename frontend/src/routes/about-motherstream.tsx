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
        <Text fontSize="lg">
          Welcome to the Motherstream. 
        </Text>
        <Text>
        {"\n"}
          The motherstream enables the always 12 collective to have a distributed group of DJ's that can be located in any part of the world, 
          queue up to broadcast their stream to the always 12 fan base. It enables a seamless transition between two DJ's in different locations with two entirely different setups.
          Something that was previously not possible with current stream platforms. In essence then the motherstream can be described as a platform that sits on top of a streaming platform, 
          extending the functionality in whatever which way we want. 
          {"\n"}
        </Text>
        <Text>
          Want to play a set? Make an account and join our discord!
        </Text>
      </VStack>
    </Container>
  );
}