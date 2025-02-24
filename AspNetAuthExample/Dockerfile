# See https://aka.ms/customizecontainer for information on how to customize the debug container and how Visual Studio uses this Dockerfile to build images for faster debugging.

# This phase is used when running from Visual Studio in Quick mode (the default for debug configuration)
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS base
USER $APP_UID
WORKDIR /app
EXPOSE 80


# This stage is used to compile the service project
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["AspNetAuthExample.csproj", "."]
RUN dotnet restore "./AspNetAuthExample.csproj"
COPY . .
WORKDIR "/src/."
RUN dotnet build "./AspNetAuthExample.csproj" -c $BUILD_CONFIGURATION -o /app/build

# This stage is used to publish the service project to be copied in the final stage
FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./AspNetAuthExample.csproj" -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

# This phase is used in the production environment or when running from Visual Studio in normal mode (the default when not using the debug configuration)
FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "AspNetAuthExample.dll"]
