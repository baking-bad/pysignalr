# Use the official ASP.NET Core runtime as a parent image
FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS base
WORKDIR /app
EXPOSE 80

# Use the SDK image to build and publish the app
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /src
COPY ["AspNetAuthExample.csproj", "./"]
RUN dotnet restore "AspNetAuthExample.csproj"
COPY . .
WORKDIR "/src/."
RUN dotnet build "AspNetAuthExample.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "AspNetAuthExample.csproj" -c Release -o /app/publish

# Final stage/image
FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "AspNetAuthExample.dll"]
